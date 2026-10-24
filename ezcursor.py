# -*- coding: utf-8 -*-
"""
EzCursor - con trỏ chuột tùy chỉnh cho game có con trỏ riêng (vd: Last Epoch)

- Tab "Ứng dụng": chọn ứng dụng đang chạy để áp dụng con trỏ, bấm Áp dụng
- Bấm X: thu nhỏ xuống khay hệ thống. Thoát hẳn: menu khay hoặc Ctrl+Alt+Q
Phím tắt: Ctrl+Alt+H bật/tắt, Ctrl+Alt+R đổi hình, Ctrl+Alt+1..5 đổi màu, Ctrl+Alt+Q thoát
Cài đặt lưu tại %APPDATA%\\EzCursor
"""

import atexit
import colorsys
import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
import tkinter as tk
import winreg
from ctypes import wintypes
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import pystray
from PIL import Image, ImageDraw, ImageTk

APP_NAME = "EzCursor"
APP_VERSION = "1.0.0"

# ======== SỬA DÒNG NÀY thành repository GitHub của bạn (tên-tài-khoản/tên-repo) ========
GITHUB_REPO = "Columbustrade/EzCursor"
# =========================================================================================
UPDATE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# ---------------------------------------------------------------- Windows API
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x08000000
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOACTIVATE = 0x1, 0x10
VK_CONTROL, VK_MENU = 0x11, 0x12
ERROR_ALREADY_EXISTS = 183
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

mag = ctypes.windll.magnification
mag.MagInitialize()
_cursor_shown = True


def show_real_cursor(show):
    global _cursor_shown
    show = bool(show)
    if show != _cursor_shown:
        mag.MagShowSystemCursor(show)
        _cursor_shown = show


def cleanup():
    try:
        mag.MagShowSystemCursor(True)
        mag.MagUninitialize()
    except Exception:
        pass


atexit.register(cleanup)


def key_down(vk):
    return user32.GetAsyncKeyState(vk) & 0x8000


def window_title(h):
    n = user32.GetWindowTextLengthW(h)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, buf, n + 1)
    return buf.value


def pid_of(h):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return pid.value


_name_cache = {}


def exe_name(pid):
    """Tên file chạy của tiến trình, vd 'Last Epoch.exe' (có cache)."""
    if pid in _name_cache:
        return _name_cache[pid]
    name = ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = os.path.basename(buf.value)
        kernel32.CloseHandle(h)
    if len(_name_cache) > 300:
        _name_cache.clear()
    if name:
        _name_cache[pid] = name
    return name


def foreground_exe():
    h = user32.GetForegroundWindow()
    return exe_name(pid_of(h)) if h else ""


IGNORED_EXES = {"explorer.exe", "textinputhost.exe", "shellexperiencehost.exe",
                "searchhost.exe", "startmenuexperiencehost.exe", "systemsettings.exe"}


def list_running_apps():
    """Danh sách (exe, tiêu đề cửa sổ) của các ứng dụng có cửa sổ đang mở."""
    apps = {}
    me = os.getpid()

    def cb(h, _):
        if not user32.IsWindowVisible(h) or user32.GetWindow(h, GW_OWNER):
            return True
        if user32.GetWindowLongW(h, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        title = window_title(h)
        pid = pid_of(h)
        if not title or pid == me:
            return True
        name = exe_name(pid)
        if name and name.lower() not in IGNORED_EXES and name.lower() not in apps:
            apps[name.lower()] = (name, title)
        return True

    proc = EnumWindowsProc(cb)
    user32.EnumWindows(proc, 0)
    return sorted(apps.values(), key=lambda a: a[1].lower())


# ---------------------------------------------------------------- Khởi động cùng Windows
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    return f'"{exe}" "{Path(__file__).resolve()}" --tray'


def run_value_exists(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, name)
            return True
    except OSError:
        return False


def is_startup_enabled():
    return run_value_exists(APP_NAME)


def set_startup(on, name=APP_NAME):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(k, name)
            except OSError:
                pass


# ---------------------------------------------------------------- Cấu hình
APPDATA = Path(os.environ.get("APPDATA", str(Path.home())))
APP_DIR = APPDATA / APP_NAME
OLD_DIR = APPDATA / "ConTroMau"          # thư mục của bản cũ
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APP_DIR / "config.json"
SHOW_FLAG = APP_DIR / "show.flag"
QUIT_FLAG = APP_DIR / "quit.flag"   # bộ cài dùng để yêu cầu thoát

TRANSPARENT = "#010101"
PRESET_COLORS = ["#ff2828", "#28ff28", "#00c8ff", "#ffe600", "#ff00dc"]
SHAPES = ["Mũi tên", "Vòng tròn", "Dấu thập", "Chấm tròn", "Kim cương", "Ảnh tải lên"]
HOTSPOTS = ["Giữa ảnh", "Góc trên trái"]
ARROW_TIP = 3
PREVIEW = 170

DEFAULT_CFG = {
    "color": PRESET_COLORS[0],
    "shape": "Vòng tròn",
    "size": 64,
    "image": "",
    "hotspot": HOTSPOTS[0],
    "tint_image": True,
    "hide_real": True,
    "enabled": True,
    "all_apps": False,
    "apps": ["Last Epoch.exe"],
    "tray_hint_shown": False,
    "auto_check_update": True,
    "last_update_check": 0,
    "skipped_version": "",
}


def migrate_old_version():
    """Chuyển cài đặt từ bản 'Con Trỏ Màu' cũ sang EzCursor (chỉ làm 1 lần)."""
    if CONFIG_PATH.exists() or not (OLD_DIR / "config.json").exists():
        return
    for f in OLD_DIR.iterdir():
        if f.is_file() and f.name != "show.flag":
            try:
                shutil.copy2(f, APP_DIR / f.name)
            except OSError:
                pass
    try:
        old = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if "game_only" in old:
            old["all_apps"] = not old["game_only"]
        CONFIG_PATH.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    if run_value_exists("ConTroMau"):     # chuyển luôn chế độ khởi động cùng Windows
        try:
            set_startup(False, "ConTroMau")
            set_startup(True)
        except OSError:
            pass


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    if cfg["shape"] not in SHAPES:
        cfg["shape"] = DEFAULT_CFG["shape"]
    if cfg["hotspot"] not in HOTSPOTS:
        cfg["hotspot"] = HOTSPOTS[0]
    cfg["size"] = max(24, min(160, int(cfg["size"])))
    if not isinstance(cfg["apps"], list):
        cfg["apps"] = list(DEFAULT_CFG["apps"])
    if cfg["image"] and not Path(cfg["image"]).exists():
        alt = APP_DIR / Path(cfg["image"]).name
        cfg["image"] = str(alt) if alt.exists() else ""
    return cfg


# ---------------------------------------------------------------- Vẽ
def draw_cursor(cv, size, shape, color, img, hotspot):
    cv.delete("all")
    m = size / 2
    if shape == "Ảnh tải lên" and img is None:
        shape = "Vòng tròn"
    if shape == "Mũi tên":
        k = (size - 6) / 32
        pts = [(1, 1), (1, 24), (7, 18), (11, 28), (15, 26), (11, 17), (19, 17)]
        flat = [v * k + ARROW_TIP - k for p in pts for v in p]
        cv.create_polygon(flat, fill=color, outline="black", width=2)
    elif shape == "Vòng tròn":
        r = m - 4
        cv.create_oval(m - r, m - r, m + r, m + r, outline="black", width=7)
        cv.create_oval(m - r, m - r, m + r, m + r, outline=color, width=4)
        cv.create_oval(m - 4, m - 4, m + 4, m + 4, fill=color, outline="black", width=2)
    elif shape == "Dấu thập":
        gap, end = max(4, size / 10), m - 3
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            line = (m + dx * gap, m + dy * gap, m + dx * end, m + dy * end)
            cv.create_line(*line, fill="black", width=7)
            cv.create_line(*line, fill=color, width=3)
        cv.create_oval(m - 3, m - 3, m + 3, m + 3, fill=color, outline="black")
    elif shape == "Chấm tròn":
        r = size / 6
        cv.create_oval(m - r, m - r, m + r, m + r, fill=color, outline="black", width=3)
    elif shape == "Kim cương":
        r = m - 6
        cv.create_polygon(m, m - r, m + r, m, m, m + r, m - r, m,
                          fill=color, outline="black", width=3)
        cv.create_oval(m - 3, m - 3, m + 3, m + 3, fill="black", outline="")
    elif shape == "Ảnh tải lên":
        if hotspot == "Góc trên trái":
            cv.create_image(0, 0, image=img, anchor="nw")
        else:
            cv.create_image(m, m, image=img)


def tint_image(im, color):
    """Đổi phần có màu của ảnh sang màu đã chọn, giữ nguyên phần trắng/đen/xám."""
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    th, ts, tv = colorsys.rgb_to_hsv(r, g, b)
    alpha = im.getchannel("A")
    rgb = im.convert("RGB")
    h, s, v = rgb.convert("HSV").split()
    mask = s.point(lambda x: 255 if x > 70 else 0)          # chỉ đổi pixel có màu
    nh = Image.new("L", im.size, int(th * 255))
    ns = s.point(lambda x: int(x * ts))
    nv = v.point(lambda x: int(x * tv))
    colored = Image.merge("HSV", (nh, ns, nv)).convert("RGB")
    out = Image.composite(colored, rgb, mask)
    out.putalpha(alpha)
    return out


def parse_version(v):
    parts = []
    for p in v.strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple((parts + [0, 0, 0])[:3])


def update_configured():
    return not GITHUB_REPO.upper().startswith("TEN-TAI-KHOAN")


def fetch_latest_release():
    req = urllib.request.Request(UPDATE_API, headers={
        "User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), None)
    return {
        "version": data.get("tag_name", "").lstrip("vV"),
        "notes": data.get("body") or "",
        "url": asset["browser_download_url"] if asset else "",
        "size": asset.get("size", 0) if asset else 0,
        "page": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
    }


def make_tray_icon():
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(4, 3), (61, 32), (61, 61), (32, 61)]
    d.polygon(pts, fill=(255, 20, 150, 255))
    d.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=5, joint="curve")
    return im


# ---------------------------------------------------------------- Ứng dụng
class App:
    def __init__(self, start_in_tray):
        self.cfg = load_cfg()
        self.enabled = bool(self.cfg["enabled"])
        self.active = False
        self.src_img = None
        self.img_tk = None
        self.prev_keys = set()
        self.tick_count = 0
        self.q = queue.Queue()
        self.list_items = []
        self.checking_update = False
        self.pending_update = None
        self.update_app_set()

        # Overlay
        self.ov = tk.Tk()
        self.ov.overrideredirect(True)
        self.ov.attributes("-topmost", True)
        self.ov.attributes("-transparentcolor", TRANSPARENT)
        self.ov.config(bg=TRANSPARENT)
        s = self.cfg["size"]
        self.ov.geometry(f"{s}x{s}+0+0")
        self.cv = tk.Canvas(self.ov, width=s, height=s, bg=TRANSPARENT, highlightthickness=0)
        self.cv.pack()
        self.ov.update_idletasks()
        self.hwnd = user32.GetParent(self.ov.winfo_id())
        st = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT
                              | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)

        # Cửa sổ điều khiển
        self.win = tk.Toplevel(self.ov)
        self.win.title(f"{APP_NAME} {APP_VERSION}")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.build_ui()
        if start_in_tray:
            self.win.withdraw()

        if self.cfg["image"]:
            self.load_image(self.cfg["image"], silent=True)

        menu = pystray.Menu(
            pystray.MenuItem("Mở EzCursor", lambda i, it: self.q.put("show"), default=True),
            pystray.MenuItem("Bật con trỏ", lambda i, it: self.q.put("toggle"),
                             checked=lambda it: self.enabled),
            pystray.MenuItem("Kiểm tra cập nhật", lambda i, it: self.q.put("check_update")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Thoát", lambda i, it: self.q.put("quit")),
        )
        self.icon = pystray.Icon(APP_NAME, make_tray_icon(), APP_NAME, menu)
        self.icon.run_detached()

        self.refresh_apps()
        self.refresh()
        self.tick()
        self.ov.after(5000, self.auto_check_update)

    # ------------------------------------------------------------ Giao diện
    def build_ui(self):
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 10))
        self.btn_toggle = ttk.Button(top, command=self.toggle)
        self.btn_toggle.pack(fill="x", ipady=4)
        self.status = ttk.Label(top, foreground="gray")
        self.status.pack(anchor="w", pady=(4, 0))

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        nb.add(self.build_cursor_tab(nb), text="  Con trỏ  ")
        nb.add(self.build_apps_tab(nb), text="  Ứng dụng  ")
        nb.add(self.build_options_tab(nb), text="  Tùy chọn  ")

    def build_cursor_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        self.preview = tk.Canvas(f, width=PREVIEW, height=PREVIEW, bg="#2b2b2b", highlightthickness=0)
        self.preview.grid(row=0, column=0, sticky="n", padx=(0, 14))

        r = ttk.Frame(f)
        r.grid(row=0, column=1, sticky="nw")
        ttk.Label(r, text="Hình dạng").grid(row=0, column=0, sticky="w")
        self.shape_var = tk.StringVar(value=self.cfg["shape"])
        cb = ttk.Combobox(r, textvariable=self.shape_var, values=SHAPES, state="readonly", width=18)
        cb.grid(row=1, column=0, sticky="w", pady=(0, 8))
        cb.bind("<<ComboboxSelected>>", lambda e: self.set_shape(self.shape_var.get()))

        ttk.Label(r, text="Màu").grid(row=2, column=0, sticky="w")
        cf = ttk.Frame(r)
        cf.grid(row=3, column=0, sticky="w", pady=(0, 8))
        for i, c in enumerate(PRESET_COLORS):
            tk.Button(cf, bg=c, activebackground=c, width=2, relief="flat",
                      command=lambda c=c: self.set_color(c)).grid(row=0, column=i, padx=2)
        ttk.Button(cf, text="Màu khác...", command=self.pick_color).grid(row=0, column=5, padx=(6, 0))

        ttk.Label(r, text="Kích thước").grid(row=4, column=0, sticky="w")
        self.size_var = tk.IntVar(value=self.cfg["size"])
        tk.Scale(r, from_=24, to=160, orient="horizontal", variable=self.size_var, length=220,
                 command=lambda v: self.set_size(int(float(v)))).grid(row=5, column=0, sticky="w", pady=(0, 8))

        ttk.Label(r, text="Ảnh con trỏ (nên dùng PNG nền trong suốt)").grid(row=6, column=0, sticky="w")
        imf = ttk.Frame(r)
        imf.grid(row=7, column=0, sticky="w")
        ttk.Button(imf, text="📁 Tải ảnh lên...", command=self.upload_image).grid(row=0, column=0)
        self.img_label = ttk.Label(imf, text="(chưa có ảnh)", foreground="gray")
        self.img_label.grid(row=0, column=1, padx=8)

        ttk.Label(r, text="Điểm click của ảnh").grid(row=8, column=0, sticky="w", pady=(8, 0))
        self.hot_var = tk.StringVar(value=self.cfg["hotspot"])
        hc = ttk.Combobox(r, textvariable=self.hot_var, values=HOTSPOTS, state="readonly", width=18)
        hc.grid(row=9, column=0, sticky="w")
        hc.bind("<<ComboboxSelected>>", lambda e: self.set_hotspot(self.hot_var.get()))

        self.tint_var = tk.BooleanVar(value=self.cfg["tint_image"])
        ttk.Checkbutton(r, text="Tô màu đã chọn cho ảnh", variable=self.tint_var,
                        command=self.set_tint).grid(row=10, column=0, sticky="w", pady=(8, 0))
        return f

    def build_apps_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        ttk.Label(f, text="Chọn ứng dụng / game sẽ dùng con trỏ của EzCursor rồi bấm Áp dụng.\n"
                          "Giữ Ctrl để chọn nhiều ứng dụng. Mở game trước rồi bấm Làm mới.",
                  justify="left").pack(anchor="w")

        lf = ttk.Frame(f)
        lf.pack(fill="both", expand=True, pady=8)
        self.app_list = tk.Listbox(lf, selectmode="extended", height=11, width=62,
                                   exportselection=False, activestyle="none")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.app_list.yview)
        self.app_list.config(yscrollcommand=sb.set)
        self.app_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        bf = ttk.Frame(f)
        bf.pack(fill="x")
        ttk.Button(bf, text="↻ Làm mới danh sách", command=self.refresh_apps).pack(side="left")
        ttk.Button(bf, text="✔ Áp dụng", command=self.apply_apps).pack(side="right")

        self.applied_label = ttk.Label(f, foreground="gray", wraplength=440, justify="left")
        self.applied_label.pack(anchor="w", pady=(8, 0))

        self.all_var = tk.BooleanVar(value=self.cfg["all_apps"])
        ttk.Checkbutton(f, text="Áp dụng cho mọi ứng dụng (kể cả Desktop)", variable=self.all_var,
                        command=self.set_all_apps).pack(anchor="w", pady=(6, 0))
        self.update_applied_label()
        return f

    def build_options_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        self.hide_var = tk.BooleanVar(value=self.cfg["hide_real"])
        ttk.Checkbutton(f, text="Ẩn con trỏ thật của game", variable=self.hide_var,
                        command=self.set_hide).pack(anchor="w")
        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        ttk.Checkbutton(f, text="Khởi động cùng Windows (chạy ngầm dưới khay)", variable=self.startup_var,
                        command=self.set_startup_opt).pack(anchor="w", pady=(6, 0))

        ttk.Separator(f).pack(fill="x", pady=12)
        uf = ttk.Frame(f)
        uf.pack(fill="x")
        ttk.Label(uf, text=f"Phiên bản: {APP_VERSION}").pack(side="left")
        ttk.Button(uf, text="Kiểm tra cập nhật", command=lambda: self.check_update(manual=True)).pack(side="right")
        self.upd_label = ttk.Label(f, foreground="gray")
        self.upd_label.pack(anchor="w", pady=(4, 0))
        self.auto_upd_var = tk.BooleanVar(value=self.cfg["auto_check_update"])
        ttk.Checkbutton(f, text="Tự động kiểm tra phiên bản mới", variable=self.auto_upd_var,
                        command=self.set_auto_update).pack(anchor="w", pady=(4, 0))
        ttk.Separator(f).pack(fill="x", pady=12)
        ttk.Label(f, foreground="gray", justify="left", text=(
            "Bấm X: thu nhỏ xuống khay hệ thống (cạnh đồng hồ).\n"
            "Thoát hẳn: chuột phải icon ở khay → Thoát.\n\n"
            "Phím tắt:\n"
            "  Ctrl+Alt+H     bật / tắt\n"
            "  Ctrl+Alt+R     đổi hình dạng\n"
            "  Ctrl+Alt+1..5  đổi màu\n"
            "  Ctrl+Alt+Q     thoát\n\n"
            "Game cần để chế độ Borderless hoặc Windowed.")).pack(anchor="w")
        return f

    # ------------------------------------------------------------ Danh sách ứng dụng
    def update_app_set(self):
        self.app_set = {a.lower() for a in self.cfg["apps"]}

    def refresh_apps(self):
        _name_cache.clear()
        running = list_running_apps()
        running_names = {n.lower() for n, _ in running}
        self.app_list.delete(0, "end")
        self.list_items = []
        for name, title in running:
            t = title if len(title) <= 45 else title[:42] + "..."
            self.app_list.insert("end", f"{t}   —   {name}")
            self.list_items.append(name)
        for name in self.cfg["apps"]:           # app đã chọn nhưng đang không chạy
            if name.lower() not in running_names:
                self.app_list.insert("end", f"(đang không chạy)   —   {name}")
                self.app_list.itemconfig("end", foreground="gray")
                self.list_items.append(name)
        for i, name in enumerate(self.list_items):
            if name.lower() in self.app_set:
                self.app_list.selection_set(i)

    def apply_apps(self):
        self.cfg["apps"] = [self.list_items[i] for i in self.app_list.curselection()]
        self.update_app_set()
        self.update_applied_label(just_applied=True)
        self.refresh()

    def update_applied_label(self, just_applied=False):
        if self.cfg["apps"]:
            txt = "Đang áp dụng cho: " + ", ".join(self.cfg["apps"])
        else:
            txt = "Chưa chọn ứng dụng nào."
        if just_applied:
            txt = "✔ Đã áp dụng. " + txt
        self.applied_label.config(text=txt)

    def set_all_apps(self):
        self.cfg["all_apps"] = bool(self.all_var.get())
        self.refresh()

    # ------------------------------------------------------------ Trạng thái
    def save(self):
        self.cfg["enabled"] = self.enabled
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def update_status(self):
        if not self.enabled:
            txt = "Đang tắt"
        elif self.active:
            txt = "Đang hoạt động"
        elif self.cfg["all_apps"]:
            txt = "Đang bật"
        elif not self.cfg["apps"]:
            txt = "Chưa chọn ứng dụng nào — vào tab Ứng dụng để chọn"
        else:
            txt = "Đang chờ: " + ", ".join(self.cfg["apps"])
        self.status.config(text=txt)

    def refresh(self):
        c = self.cfg
        self.btn_toggle.config(text="■ Tắt EzCursor" if self.enabled else "▶ Bật EzCursor")
        if self.active:
            draw_cursor(self.cv, c["size"], c["shape"], c["color"], self.img_tk, c["hotspot"])
        else:
            self.cv.delete("all")
        draw_cursor(self.preview, c["size"], c["shape"], c["color"], self.img_tk, c["hotspot"])
        d = (PREVIEW - c["size"]) / 2
        self.preview.move("all", d, d)
        self.update_status()
        self.save()

    def compute_active(self):
        if not self.enabled:
            return False
        if self.cfg["all_apps"]:
            return True
        return bool(self.app_set) and foreground_exe().lower() in self.app_set

    def set_active(self, on):
        if on == self.active:
            return
        self.active = on
        show_real_cursor(not (on and self.cfg["hide_real"]))
        self.refresh()

    # ------------------------------------------------------------ Hành động
    def toggle(self):
        self.enabled = not self.enabled
        self.set_active(self.compute_active())
        self.refresh()
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def set_shape(self, shape):
        self.cfg["shape"] = shape
        self.shape_var.set(shape)
        self.refresh()

    def next_shape(self):
        options = SHAPES if self.img_tk is not None else SHAPES[:-1]
        cur = self.cfg["shape"]
        i = options.index(cur) if cur in options else -1
        self.set_shape(options[(i + 1) % len(options)])

    def set_color(self, color):
        if color.lower() == TRANSPARENT:
            color = "#020202"
        self.cfg["color"] = color
        self.rebuild_image()
        self.refresh()

    def pick_color(self):
        res = colorchooser.askcolor(color=self.cfg["color"], parent=self.win, title="Chọn màu")
        if res and res[1]:
            self.set_color(res[1])

    def set_size(self, s):
        self.cfg["size"] = s
        self.ov.geometry(f"{s}x{s}")
        self.cv.config(width=s, height=s)
        self.rebuild_image()
        self.refresh()

    def set_tint(self):
        self.cfg["tint_image"] = bool(self.tint_var.get())
        self.rebuild_image()
        self.refresh()

    def set_hotspot(self, h):
        self.cfg["hotspot"] = h
        self.refresh()

    def set_hide(self):
        self.cfg["hide_real"] = bool(self.hide_var.get())
        show_real_cursor(not (self.active and self.cfg["hide_real"]))
        self.save()

    def set_startup_opt(self):
        try:
            set_startup(self.startup_var.get())
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thay đổi được cài đặt khởi động:\n{e}", parent=self.win)
            self.startup_var.set(is_startup_enabled())

    def upload_image(self):
        path = filedialog.askopenfilename(
            parent=self.win, title="Chọn ảnh con trỏ",
            filetypes=[("Ảnh", "*.png *.gif *.webp *.ico *.bmp *.jpg *.jpeg"), ("Tất cả", "*.*")])
        if not path:
            return
        dest = APP_DIR / ("custom" + Path(path).suffix.lower())
        try:
            shutil.copyfile(path, dest)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không sao chép được ảnh:\n{e}", parent=self.win)
            return
        if self.load_image(str(dest)):
            self.cfg["image"] = str(dest)
            self.set_shape("Ảnh tải lên")

    def load_image(self, path, silent=False):
        try:
            self.src_img = Image.open(path).convert("RGBA")
        except Exception as e:
            self.src_img = None
            if not silent:
                messagebox.showerror("Lỗi", f"Không mở được ảnh:\n{e}", parent=self.win)
            return False
        self.rebuild_image()
        self.img_label.config(text=Path(path).name, foreground="")
        return True

    def rebuild_image(self):
        if self.src_img is None:
            self.img_tk = None
            return
        s = self.cfg["size"]
        w, h = self.src_img.size
        k = s / max(w, h)
        im = self.src_img.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
        if self.cfg["tint_image"]:
            im = tint_image(im, self.cfg["color"])
        im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
        self.img_tk = ImageTk.PhotoImage(im, master=self.ov)

    def hotspot_offset(self):
        c = self.cfg
        if c["shape"] == "Mũi tên":
            return ARROW_TIP, ARROW_TIP
        if c["shape"] == "Ảnh tải lên" and self.img_tk is not None and c["hotspot"] == "Góc trên trái":
            return 0, 0
        return c["size"] // 2, c["size"] // 2

    def hide_to_tray(self):
        self.win.withdraw()
        if not self.cfg["tray_hint_shown"]:
            self.cfg["tray_hint_shown"] = True
            self.save()
            try:
                self.icon.notify("EzCursor vẫn đang chạy dưới khay hệ thống. "
                                 "Chuột phải vào icon để mở lại hoặc thoát.", APP_NAME)
            except Exception:
                pass

    def show_window(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        if self.pending_update:
            info, self.pending_update = self.pending_update, None
            self.show_update_dialog(info, manual=False)

    # ------------------------------------------------------------ Cập nhật
    def set_auto_update(self):
        self.cfg["auto_check_update"] = bool(self.auto_upd_var.get())
        self.save()

    def auto_check_update(self):
        if (self.cfg["auto_check_update"] and update_configured()
                and time.time() - self.cfg["last_update_check"] > 20 * 3600):
            self.check_update(manual=False)
        self.ov.after(6 * 3600 * 1000, self.auto_check_update)   # kiểm tra lại sau 6 giờ

    def check_update(self, manual):
        if not update_configured():
            if manual:
                messagebox.showinfo(APP_NAME, "Chưa cấu hình GITHUB_REPO trong mã nguồn.", parent=self.win)
            return
        if self.checking_update:
            return
        self.checking_update = True
        self.upd_label.config(text="Đang kiểm tra cập nhật...")

        def work():
            try:
                self.q.put(("update_result", fetch_latest_release(), manual))
            except Exception as e:
                self.q.put(("update_error", str(e), manual))
        threading.Thread(target=work, daemon=True).start()

    def handle_update_msg(self, kind, data=None, manual=False):
        if kind == "update_result":
            self.checking_update = False
            self.cfg["last_update_check"] = time.time()
            self.save()
            info = data
            if parse_version(info["version"]) <= parse_version(APP_VERSION):
                self.upd_label.config(text="Bạn đang dùng phiên bản mới nhất.")
                if manual:
                    messagebox.showinfo(APP_NAME, f"Bạn đang dùng phiên bản mới nhất ({APP_VERSION}).",
                                        parent=self.win)
                return
            self.upd_label.config(text=f"Có phiên bản mới: {info['version']}")
            if not manual and info["version"] == self.cfg["skipped_version"]:
                return
            if self.win.state() == "withdrawn":
                # đang chạy ngầm (có thể đang chơi game): chỉ báo nhẹ, không bật cửa sổ
                self.pending_update = info
                try:
                    self.icon.notify(f"Đã có EzCursor {info['version']}. Mở EzCursor để cập nhật.", APP_NAME)
                except Exception:
                    pass
            else:
                self.show_update_dialog(info, manual)
        elif kind == "update_error":
            self.checking_update = False
            self.upd_label.config(text="Không kiểm tra được cập nhật.")
            if manual:
                messagebox.showerror(APP_NAME, f"Không kiểm tra được cập nhật.\nHãy kiểm tra kết nối mạng.\n\n{data}",
                                     parent=self.win)
        elif kind == "dl_progress":
            self.dl_bar["value"] = data
            self.dl_label.config(text=f"Đang tải... {data:.0f}%")
        elif kind == "dl_done":
            self.dl_label.config(text="Đang cài đặt, EzCursor sẽ tự mở lại sau giây lát...")
            try:
                subprocess.Popen([data, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH"])
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Không chạy được bộ cài:\n{e}", parent=self.upd_dialog)
                return
            self.ov.after(500, self.quit)
        elif kind == "dl_error":
            self.btn_update.config(state="normal")
            self.dl_label.config(text="Tải về thất bại.")
            messagebox.showerror(APP_NAME, f"Tải bản cập nhật thất bại:\n{data}", parent=self.upd_dialog)

    def show_update_dialog(self, info, manual):
        d = tk.Toplevel(self.ov)
        d.title(f"{APP_NAME} - Cập nhật")
        d.resizable(False, False)
        d.attributes("-topmost", True)
        self.upd_dialog = d
        frm = ttk.Frame(d, padding=14)
        frm.pack(fill="both")
        ttk.Label(frm, text=f"Đã có EzCursor {info['version']}  (bạn đang dùng {APP_VERSION})",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(frm, text="Có gì mới:").pack(anchor="w", pady=(8, 2))
        txt = tk.Text(frm, width=62, height=12, wrap="word", relief="solid", borderwidth=1)
        txt.insert("1.0", info["notes"].strip() or "(không có ghi chú)")
        txt.config(state="disabled")
        txt.pack(fill="both")
        self.dl_bar = ttk.Progressbar(frm, mode="determinate", maximum=100)
        self.dl_bar.pack(fill="x", pady=(10, 0))
        self.dl_label = ttk.Label(frm, foreground="gray")
        self.dl_label.pack(anchor="w")
        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(10, 0))
        if info["url"]:
            self.btn_update = ttk.Button(bf, text="⬇ Cập nhật ngay", command=lambda: self.start_download(info))
        else:
            self.btn_update = ttk.Button(bf, text="Mở trang tải về",
                                         command=lambda: webbrowser.open(info["page"]))
        self.btn_update.pack(side="right")
        ttk.Button(bf, text="Để sau", command=d.destroy).pack(side="right", padx=6)
        if not manual:
            def skip():
                self.cfg["skipped_version"] = info["version"]
                self.save()
                d.destroy()
            ttk.Button(bf, text="Bỏ qua phiên bản này", command=skip).pack(side="left")
        d.lift()
        d.focus_force()

    def start_download(self, info):
        self.btn_update.config(state="disabled")
        dest = Path(tempfile.gettempdir()) / f"EzCursor_Setup_{info['version']}.exe"

        def work():
            try:
                req = urllib.request.Request(info["url"], headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
                with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
                    total = int(r.headers.get("Content-Length") or info["size"] or 0)
                    done = 0
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.q.put(("dl_progress", min(100.0, done * 100 / total)))
                self.q.put(("dl_done", str(dest)))
            except Exception as e:
                self.q.put(("dl_error", str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ Vòng lặp
    def check_hotkeys(self):
        now = set()
        if key_down(VK_CONTROL) and key_down(VK_MENU):
            for ch in "12345RHQ":
                if key_down(ord(ch)):
                    now.add(ch)
        for ch in now - self.prev_keys:
            if ch.isdigit():
                self.set_color(PRESET_COLORS[int(ch) - 1])
            elif ch == "R":
                self.next_shape()
            elif ch == "H":
                self.toggle()
            elif ch == "Q":
                self.quit()
                return False
        self.prev_keys = now
        return True

    def process_queue(self):
        while not self.q.empty():
            cmd = self.q.get()
            if isinstance(cmd, tuple):
                self.handle_update_msg(*cmd)
                continue
            if cmd == "check_update":
                self.show_window()
                self.check_update(manual=True)
            elif cmd == "show":
                self.show_window()
            elif cmd == "toggle":
                self.toggle()
            elif cmd == "quit":
                self.quit()
                return False
        return True

    def tick(self):
        if not self.process_queue() or not self.check_hotkeys():
            return
        self.tick_count += 1
        if self.tick_count % 25 == 0 and SHOW_FLAG.exists():
            try:
                SHOW_FLAG.unlink()
            except OSError:
                pass
            self.show_window()
        if self.tick_count % 25 == 0 and QUIT_FLAG.exists():
            try:
                QUIT_FLAG.unlink()
            except OSError:
                pass
            self.quit()
            return
        self.set_active(self.compute_active())
        if self.active:
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            dx, dy = self.hotspot_offset()
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, pt.x - dx, pt.y - dy, 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE)
        self.ov.after(4, self.tick)

    def quit(self):
        cleanup()
        self.save()
        try:
            self.icon.stop()
        except Exception:
            pass
        self.ov.destroy()


def main():
    kernel32.CreateMutexW(None, False, "EzCursor_SingleInstance")
    already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    if "--quit" in sys.argv:          # dùng bởi bộ cài: yêu cầu bản đang chạy thoát
        if already_running:
            QUIT_FLAG.touch()
        return
    if already_running:
        if "--tray" not in sys.argv:
            SHOW_FLAG.touch()
        return
    for flag in (SHOW_FLAG, QUIT_FLAG):
        try:
            flag.unlink()
        except OSError:
            pass
    migrate_old_version()
    app = App(start_in_tray="--tray" in sys.argv)
    app.ov.mainloop()


if __name__ == "__main__":
    main()

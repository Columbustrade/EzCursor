# -*- coding: utf-8 -*-
"""
EzCursor - con trỏ chuột tùy chỉnh cho game có con trỏ riêng (vd: Last Epoch)

- Giao diện Neon HUD (CustomTkinter)
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
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw, ImageFilter, ImageTk

APP_NAME = "EzCursor"
APP_VERSION = "1.1.0"

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


# ---------------------------------------------------------------- Giao diện Neon HUD
BG = "#0B0D12"
SIDEBAR = "#0D0F15"
CARD = "#12151D"
FIELD = "#0E1117"
BORDER = "#262B38"
LINE = "#1E2330"
TEXT = "#E8EAF0"
TEXT2 = "#A3ABBD"
MUTED = "#8B93A7"
ACCENT = "#FF1F8F"
CYAN = "#22D3EE"
CYAN_TEXT = "#67E8F9"
GREEN = "#3BE58F"
AMBER = "#FFB020"
SWATCHES = [("#FF1F8F", "Hồng neon"), ("#FF3B3B", "Đỏ"), ("#3BE58F", "Xanh lá"),
            ("#22D3EE", "Xanh cyan"), ("#FFD60A", "Vàng"), ("#A855F7", "Tím")]
# Ctrl+Alt+1..5 dùng 5 màu đầu
PRESET_COLORS = [c for c, _ in SWATCHES[:5]]

SHAPE_BUTTONS = [("Mũi tên", "Mũi tên"), ("Vòng tròn", "Vòng tròn"), ("Dấu thập", "Dấu thập"),
                 ("Chấm tròn", "Chấm tròn"), ("Kim cương", "Kim cương"), ("Ảnh tải lên", "Ảnh")]


def res_path(*parts):
    """Đường dẫn tới file đi kèm (chạy thường hoặc trong exe PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def mix(c1, c2, t):
    """Trộn màu c1 với c2 theo tỉ lệ t (0 = c1, 1 = c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def load_fonts():
    for f in ("ChakraPetch-Bold.ttf", "ChakraPetch-SemiBold.ttf",
              "BeVietnamPro-Regular.ttf", "BeVietnamPro-SemiBold.ttf"):
        p = res_path("fonts", f)
        if p.exists():
            try:
                ctk.FontManager.load_font(str(p))
            except Exception:
                pass


class Fonts:
    def __init__(self, root):
        import tkinter.font as tkfont
        fam = set(tkfont.families(root))
        self.head = "Chakra Petch" if "Chakra Petch" in fam else "Segoe UI"
        self.body = "Be Vietnam Pro" if "Be Vietnam Pro" in fam else "Segoe UI"
        self.body_b = "Be Vietnam Pro SemiBold" if "Be Vietnam Pro SemiBold" in fam else "Segoe UI Semibold"
        self.mono = "Consolas"

    def h(self, size, bold=True):
        return ctk.CTkFont(family=self.head, size=size, weight="bold" if bold else "normal")

    def b(self, size=13, strong=False):
        return ctk.CTkFont(family=self.body_b if strong else self.body, size=size)

    def m(self, size=11):
        return ctk.CTkFont(family=self.mono, size=size)


def _ss(draw_fn, size, scale=4):
    im = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), scale)
    return im.resize((size, size), Image.LANCZOS)


def nav_icon(kind, color, size=20):
    def draw(d, s):
        w = int(2 * s)
        if kind == "cursor":
            d.line([(4 * s, 3 * s), (17 * s, 9.5 * s), (11 * s, 11 * s), (9.5 * s, 17 * s), (4 * s, 3 * s)],
                   fill=color, width=w, joint="curve")
        elif kind == "apps":
            d.rounded_rectangle([2.5 * s, 6 * s, 17.5 * s, 15 * s], radius=3.5 * s, outline=color, width=w)
            d.line([(7 * s, 8.5 * s), (7 * s, 12.5 * s)], fill=color, width=w)
            d.line([(5 * s, 10.5 * s), (9 * s, 10.5 * s)], fill=color, width=w)
            for cx, cy in ((13 * s, 9.5 * s), (14.8 * s, 11.6 * s)):
                d.ellipse([cx - 1.1 * s, cy - 1.1 * s, cx + 1.1 * s, cy + 1.1 * s], fill=color)
        else:  # tùy chọn
            d.line([(3 * s, 6 * s), (17 * s, 6 * s)], fill=color, width=w)
            d.line([(3 * s, 14 * s), (17 * s, 14 * s)], fill=color, width=w)
            for cx, cy in ((7.5 * s, 6 * s), (12.5 * s, 14 * s)):
                d.ellipse([cx - 2.4 * s, cy - 2.4 * s, cx + 2.4 * s, cy + 2.4 * s], fill=SIDEBAR, outline=color, width=w)
    return _ss(draw, size)


def logo_image(size=26):
    def draw(d, s):
        pts = [(2 * s, 1.5 * s), (24 * s, 13 * s), (24 * s, 24 * s), (13 * s, 24 * s)]
        d.polygon(pts, fill=ACCENT)
        d.line(pts + [pts[0]], fill="#FFFFFF", width=int(2.2 * s), joint="curve")
    return _ss(draw, size)


def simple_icon(kind, color, size=16):
    def draw(d, s):
        w = int(2 * s)
        if kind == "upload":
            d.line([(8 * s, 11 * s), (8 * s, 2.5 * s)], fill=color, width=w)
            d.line([(4.5 * s, 6 * s), (8 * s, 2.5 * s), (11.5 * s, 6 * s)], fill=color, width=w, joint="curve")
            d.line([(2.5 * s, 10.5 * s), (2.5 * s, 13.5 * s), (13.5 * s, 13.5 * s), (13.5 * s, 10.5 * s)],
                   fill=color, width=w, joint="curve")
        elif kind == "refresh":
            d.arc([2.5 * s, 2.5 * s, 13.5 * s, 13.5 * s], start=-40, end=280, fill=color, width=w)
            d.line([(13.8 * s, 2 * s), (13.8 * s, 6.2 * s), (9.6 * s, 6.2 * s)], fill=color, width=w, joint="curve")
        elif kind == "plus":
            d.line([(8 * s, 3 * s), (8 * s, 13 * s)], fill=color, width=w)
            d.line([(3 * s, 8 * s), (13 * s, 8 * s)], fill=color, width=w)
    return _ss(draw, size)


def render_preview(shape, color, size, img_rgba, hotspot):
    """Vẽ con trỏ cho khung xem trước, có quầng sáng (glow)."""
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = n / 64

    def P(pts):
        return [(x * k, y * k) for x, y in pts]

    def W(v):
        return max(1, int(v * k))

    if shape == "Ảnh tải lên" and img_rgba is None:
        shape = "Vòng tròn"
    if shape == "Mũi tên":
        d.polygon(P([(3, 3), (3, 50), (15, 38), (23, 57), (31, 53), (23, 36), (40, 36)]),
                  fill=color, outline="#000000", width=W(2.5))
    elif shape == "Vòng tròn":
        d.ellipse([2.5 * k, 2.5 * k, 61.5 * k, 61.5 * k], outline="#000000", width=W(7))
        d.ellipse([4 * k, 4 * k, 60 * k, 60 * k], outline=color, width=W(4))
        d.ellipse([28 * k, 28 * k, 36 * k, 36 * k], fill=color, outline="#000000", width=W(2))
    elif shape == "Dấu thập":
        segs = [((32, 4), (32, 24)), ((32, 40), (32, 60)), ((4, 32), (24, 32)), ((40, 32), (60, 32))]
        for a, b in segs:
            d.line(P([a, b]), fill="#000000", width=W(7))
        for a, b in segs:
            d.line(P([a, b]), fill=color, width=W(3))
        d.ellipse([29 * k, 29 * k, 35 * k, 35 * k], fill=color, outline="#000000", width=W(1.5))
    elif shape == "Chấm tròn":
        d.ellipse([21 * k, 21 * k, 43 * k, 43 * k], fill=color, outline="#000000", width=W(3))
    elif shape == "Kim cương":
        d.polygon(P([(32, 6), (58, 32), (32, 58), (6, 32)]), fill=color, outline="#000000", width=W(3))
        d.ellipse([29 * k, 29 * k, 35 * k, 35 * k], fill="#000000")
    elif shape == "Ảnh tải lên":
        w, h = img_rgba.size
        f = n / max(w, h)
        pic = img_rgba.resize((max(1, round(w * f)), max(1, round(h * f))), Image.LANCZOS)
        pos = (0, 0) if hotspot == "Góc trên trái" else ((n - pic.width) // 2, (n - pic.height) // 2)
        im.alpha_composite(pic, pos)
    im = im.resize((size, size), Image.LANCZOS)

    pad = max(12, size // 3)
    out = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    alpha = Image.new("L", out.size, 0)
    alpha.paste(im.getchannel("A"), (pad, pad))
    alpha = alpha.filter(ImageFilter.GaussianBlur(max(4, size / 9))).point(lambda v: int(v * 0.85))
    glow = Image.new("RGBA", out.size, color)
    glow.putalpha(alpha)
    out.alpha_composite(glow)
    out.alpha_composite(im, (pad, pad))
    return out


# ---------------------------------------------------------------- Ứng dụng
class App:
    PW, PH = 316, 300   # kích thước khung xem trước

    def __init__(self, start_in_tray):
        self.cfg = load_cfg()
        self.enabled = bool(self.cfg["enabled"])
        self.active = False
        self.src_img = None
        self.img_tk = None
        self.prev_keys = set()
        self.tick_count = 0
        self.anim_frame = 0
        self.q = queue.Queue()
        self.app_vars = {}
        self.checking_update = False
        self.pending_update = None
        self.fg_exe = ""
        self.tab = "cursor"
        self.update_app_set()

        load_fonts()
        ctk.set_appearance_mode("dark")

        # Overlay (trong suốt, click xuyên qua, luôn trên cùng)
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

        self.F = Fonts(self.ov)

        # Cửa sổ chính
        self.win = ctk.CTkToplevel(self.ov, fg_color=BG)
        self.win.title(APP_NAME)
        self.win.geometry("1000x700")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        ico = res_path("ezcursor.ico")
        if ico.exists():
            self.win.after(260, lambda: self.win.iconbitmap(str(ico)))
        try:
            self.sc = self.win._get_window_scaling()
        except Exception:
            self.sc = 1.0

        if self.cfg["image"]:
            self.load_image(self.cfg["image"], silent=True)

        self.build_ui()
        if start_in_tray:
            self.win.withdraw()
            self.win.after(300, self.win.withdraw)

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
        self.anim()
        self.ov.after(5000, self.auto_check_update)

    # ------------------------------------------------------------ Tiện ích giao diện
    def caps(self, parent, text, color=MUTED):
        return ctk.CTkLabel(parent, text=text, font=self.F.h(11, bold=False), text_color=color)

    def card(self, parent, **kw):
        return ctk.CTkFrame(parent, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=14, **kw)

    def switch(self, parent, var, command):
        return ctk.CTkSwitch(parent, text="", variable=var, command=command, width=50,
                             switch_width=46, switch_height=24, progress_color=ACCENT, fg_color="#1A1E29",
                             button_color="#FFFFFF", button_hover_color="#FFFFFF", border_color="#3A4152")

    def cyan_button(self, parent, text, command, icon=None):
        return ctk.CTkButton(parent, text=text, command=command, image=icon, compound="left",
                             height=40, corner_radius=10, border_width=1, border_color=CYAN,
                             fg_color=mix(CARD, CYAN, 0.10), hover_color=mix(CARD, CYAN, 0.22),
                             text_color=CYAN_TEXT, font=self.F.b(13, strong=True))

    def header(self, parent, title, sub):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text=title, font=self.F.h(24), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(f, text=sub, font=self.F.b(13), text_color=TEXT2).pack(anchor="w")
        return f

    # ------------------------------------------------------------ Dựng giao diện
    def build_ui(self):
        self.win.grid_columnconfigure(1, weight=1)
        self.win.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.content = ctk.CTkFrame(self.win, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.pages = {
            "cursor": self.build_cursor_tab(self.content),
            "apps": self.build_apps_tab(self.content),
            "opts": self.build_options_tab(self.content),
        }
        self.show_tab("cursor")

    def build_sidebar(self):
        sb = ctk.CTkFrame(self.win, fg_color=SIDEBAR, corner_radius=0, width=230,
                          border_width=0)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)
        sb.pack_propagate(False)
        ctk.CTkFrame(self.win, fg_color=LINE, width=1, corner_radius=0).grid(row=0, column=0, sticky="nse")

        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(20, 18))
        ctk.CTkLabel(logo, text="", image=ctk.CTkImage(logo_image(52), size=(26, 26))).pack(side="left")
        ctk.CTkLabel(logo, text=" EZ", font=self.F.h(18), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(logo, text="CURSOR", font=self.F.h(18), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(logo, text=f"v{APP_VERSION}", font=self.F.m(10), text_color=MUTED,
                     fg_color="#151922", corner_radius=6, width=10).pack(side="left", padx=(8, 0))

        self.caps(sb, "MENU").pack(anchor="w", padx=24, pady=(0, 6))
        self.nav_buttons = {}
        for key, label in (("cursor", "Con trỏ"), ("apps", "Ứng dụng"), ("opts", "Tùy chọn")):
            icons = (ctk.CTkImage(nav_icon(key, "#FFFFFF", 40), size=(20, 20)),
                     ctk.CTkImage(nav_icon(key, TEXT2, 40), size=(20, 20)))
            b = ctk.CTkButton(sb, text="  " + label, anchor="w", height=46, corner_radius=10,
                              font=self.F.b(14, strong=True), border_width=1,
                              command=lambda k=key: self.show_tab(k))
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = (b, icons)

        # Khung trạng thái
        st = ctk.CTkFrame(sb, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=12)
        st.pack(side="bottom", fill="x", padx=14, pady=16)
        self.caps(st, "TRẠNG THÁI").pack(anchor="w", padx=14, pady=(12, 6))
        self.pill = ctk.CTkLabel(st, text="", font=self.F.h(12), corner_radius=14, height=28)
        self.pill.pack(anchor="w", padx=14)
        self.status_sub = ctk.CTkLabel(st, text="", font=self.F.b(12), text_color=TEXT2,
                                       wraplength=int(170 * 1), justify="left")
        self.status_sub.pack(anchor="w", padx=14, pady=(6, 8))
        row = ctk.CTkFrame(st, fg_color="transparent")
        row.pack(fill="x", padx=14)
        ctk.CTkLabel(row, text="Bật EzCursor", font=self.F.b(14, strong=True), text_color=TEXT).pack(side="left")
        self.enabled_var = tk.BooleanVar(value=self.enabled)
        self.switch(row, self.enabled_var, self.on_enabled_switch).pack(side="right")
        ctk.CTkLabel(st, text="Ctrl + Alt + H", font=self.F.m(11), text_color=MUTED).pack(anchor="w", padx=14, pady=(4, 12))

    def build_cursor_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.header(page, "CON TRỎ", "Chọn hình dạng, màu sắc và kích thước con trỏ trong game.").pack(anchor="w", pady=(0, 16))
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure((0, 1), weight=1, uniform="c")

        # --- Xem trước
        pv = self.card(body)
        pv.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        top = ctk.CTkFrame(pv, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 8))
        self.caps(top, "XEM TRƯỚC").pack(side="left")
        ctk.CTkLabel(top, text="LIVE", font=self.F.m(11), text_color=CYAN).pack(side="right")
        sc = self.sc
        self.pw, self.ph = int(self.PW * sc), int(self.PH * sc)
        self.pcv = tk.Canvas(pv, width=self.pw, height=self.ph, bg=FIELD, highlightthickness=1,
                             highlightbackground=BORDER, bd=0)
        self.pcv.pack(padx=14, pady=(0, 14))
        self.build_preview_canvas()

        # --- Điều khiển
        ctl = self.card(body)
        ctl.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        inner = ctk.CTkFrame(ctl, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        self.caps(inner, "HÌNH DẠNG").pack(anchor="w")
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x", pady=(6, 14))
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.shape_buttons = {}
        for i, (shape, label) in enumerate(SHAPE_BUTTONS):
            b = ctk.CTkButton(grid, text=label, height=38, corner_radius=9, border_width=1,
                              font=self.F.b(13, strong=True), command=lambda s=shape: self.set_shape(s))
            b.grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)
            self.shape_buttons[shape] = b

        self.caps(inner, "MÀU SẮC").pack(anchor="w")
        sw = ctk.CTkFrame(inner, fg_color="transparent")
        sw.pack(fill="x", pady=(6, 14))
        self.swatch_buttons = {}
        for c, name in SWATCHES:
            b = ctk.CTkButton(sw, text="", width=34, height=34, corner_radius=17, fg_color=c,
                              hover_color=mix(c, "#FFFFFF", 0.2), border_width=0,
                              command=lambda c=c: self.set_color(c))
            b.pack(side="left", padx=(0, 7))
            self.swatch_buttons[c] = b
        self.custom_btn = ctk.CTkButton(sw, text="", width=34, height=34, corner_radius=17,
                                        image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)),
                                        fg_color="transparent", hover_color="#1A1E29",
                                        border_width=1, border_color="#4A5266", command=self.pick_color)
        self.custom_btn.pack(side="left")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.caps(row, "KÍCH THƯỚC").pack(side="left")
        self.size_label = ctk.CTkLabel(row, text="", font=self.F.m(12), text_color=ACCENT)
        self.size_label.pack(side="right")
        self.size_slider = ctk.CTkSlider(inner, from_=24, to=160, number_of_steps=136,
                                         command=lambda v: self.set_size(int(v)), progress_color=ACCENT,
                                         button_color=ACCENT, button_hover_color=mix(ACCENT, "#FFFFFF", 0.25),
                                         fg_color="#1A1E29", height=18)
        self.size_slider.set(self.cfg["size"])
        self.size_slider.pack(fill="x", pady=(4, 14))

        self.caps(inner, "ẢNH TÙY CHỈNH").pack(anchor="w")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(6, 6))
        self.cyan_button(row, "Tải ảnh lên", self.upload_image,
                         ctk.CTkImage(simple_icon("upload", CYAN_TEXT, 32), size=(16, 16))).pack(side="left")
        self.img_label = ctk.CTkLabel(row, text="(chưa có ảnh)", font=self.F.m(12), text_color=TEXT2)
        self.img_label.pack(side="left", padx=10)
        if self.cfg["image"] and self.src_img is not None:
            self.img_label.configure(text=Path(self.cfg["image"]).name)

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(row, text="Điểm click", font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.hot_seg = ctk.CTkSegmentedButton(row, values=HOTSPOTS, command=self.set_hotspot, height=30,
                                              font=self.F.b(12), fg_color=FIELD, unselected_color=FIELD,
                                              unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                                              selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        self.hot_seg.set(self.cfg["hotspot"])
        self.hot_seg.pack(side="right")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(row, text="Tô màu đã chọn cho ảnh", font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.tint_var = tk.BooleanVar(value=self.cfg["tint_image"])
        self.switch(row, self.tint_var, self.set_tint).pack(side="right")
        return page

    def build_preview_canvas(self):
        c, w, h, sc = self.pcv, self.pw, self.ph, self.sc
        step = int(22 * sc)
        gcol = mix(FIELD, CYAN, 0.07)
        for x in range(w // 2 % step, w, step):
            c.create_line(x, 0, x, h, fill=gcol)
        for y in range(h // 2 % step, h, step):
            c.create_line(0, y, w, y, fill=gcol)
        L, m, t = int(18 * sc), int(12 * sc), max(2, int(2 * sc))
        for x0, y0, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            c.create_line(x0, y0, x0 + dx * L, y0, fill=CYAN, width=t)
            c.create_line(x0, y0, x0, y0 + dy * L, fill=CYAN, width=t)
        self.scan = c.create_line(0, 0, w, 0, fill=mix(FIELD, CYAN, 0.35), width=max(1, int(2 * sc)))
        self.ping = c.create_oval(0, 0, 0, 0, outline=ACCENT, width=max(2, int(2 * sc)))
        self.pimg_id = c.create_image(w // 2, h // 2)
        mono = (self.F.mono, 9)
        self.coord_txt = c.create_text(int(16 * sc), h - int(30 * sc), anchor="w", text="", fill=CYAN_TEXT, font=mono)
        self.size_txt = c.create_text(w - int(16 * sc), h - int(30 * sc), anchor="e", text="", fill=CYAN_TEXT, font=mono)

    def build_apps_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        self.header(top, "ỨNG DỤNG", "Chọn game sẽ dùng con trỏ của EzCursor, rồi bấm Áp dụng.").pack(side="left")
        self.cyan_button(top, "Làm mới", self.refresh_apps,
                         ctk.CTkImage(simple_icon("refresh", CYAN_TEXT, 32), size=(16, 16))).pack(side="right", anchor="s")

        self.app_list = ctk.CTkScrollableFrame(page, fg_color=CARD, border_color=BORDER, border_width=1,
                                               corner_radius=14, height=int(390), scrollbar_button_color=BORDER,
                                               scrollbar_button_hover_color="#3A4152")
        self.app_list.pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(page, fg_color="transparent")
        bottom.pack(fill="x", pady=(14, 0))
        self.all_var = tk.BooleanVar(value=self.cfg["all_apps"])
        self.switch(bottom, self.all_var, self.set_all_apps).pack(side="left")
        ctk.CTkLabel(bottom, text="  Áp dụng cho mọi ứng dụng (kể cả Desktop)", font=self.F.b(13),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(bottom, text="ÁP DỤNG", command=self.apply_apps, height=44, width=150, corner_radius=10,
                      fg_color=ACCENT, hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF",
                      font=self.F.h(15)).pack(side="right")
        self.applied_label = ctk.CTkLabel(page, text="", font=self.F.b(12), text_color=TEXT2, anchor="w",
                                          justify="left", wraplength=680)
        self.applied_label.pack(fill="x", pady=(10, 0))
        self.update_applied_label()
        return page

    def build_options_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.header(page, "TÙY CHỌN", "Cài đặt chung, cập nhật và phím tắt.").pack(anchor="w", pady=(0, 16))

        box = self.card(page)
        box.pack(fill="x")
        self.hide_var = tk.BooleanVar(value=self.cfg["hide_real"])
        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        self.auto_upd_var = tk.BooleanVar(value=self.cfg["auto_check_update"])
        rows = [("Ẩn con trỏ thật của game", "Chỉ hiện con trỏ của EzCursor khi đang ở trong game.",
                 self.hide_var, self.set_hide),
                ("Khởi động cùng Windows", "Chạy ngầm dưới khay hệ thống khi bật máy.",
                 self.startup_var, self.set_startup_opt),
                ("Tự động kiểm tra cập nhật", "Thông báo khi có phiên bản mới trên GitHub.",
                 self.auto_upd_var, self.set_auto_update)]
        for title, sub, var, cmd in rows:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=18, pady=(10, 0))
            t = ctk.CTkFrame(r, fg_color="transparent")
            t.pack(side="left")
            ctk.CTkLabel(t, text=title, font=self.F.b(14, strong=True), text_color=TEXT, height=20).pack(anchor="w")
            ctk.CTkLabel(t, text=sub, font=self.F.b(12), text_color=TEXT2, height=18).pack(anchor="w")
            self.switch(r, var, cmd).pack(side="right")
            ctk.CTkFrame(box, fg_color=LINE, height=1, corner_radius=0).pack(fill="x", padx=18, pady=(10, 0))

        r = ctk.CTkFrame(box, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=12)
        t = ctk.CTkFrame(r, fg_color="transparent")
        t.pack(side="left")
        v = ctk.CTkFrame(t, fg_color="transparent")
        v.pack(anchor="w")
        ctk.CTkLabel(v, text="Phiên bản ", font=self.F.b(14, strong=True), text_color=TEXT, height=20).pack(side="left")
        ctk.CTkLabel(v, text=APP_VERSION, font=self.F.m(13), text_color=ACCENT, height=20).pack(side="left")
        self.upd_label = ctk.CTkLabel(t, text="", font=self.F.b(12), text_color=TEXT2, height=18)
        self.upd_label.pack(anchor="w")
        self.cyan_button(r, "Kiểm tra cập nhật", lambda: self.check_update(manual=True)).pack(side="right")

        hk = self.card(page)
        hk.pack(fill="x", pady=(16, 0))
        self.caps(hk, "PHÍM TẮT").pack(anchor="w", padx=16, pady=(12, 6))
        grid = ctk.CTkFrame(hk, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 12))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="h")
        keys = [("Bật / tắt", "H"), ("Đổi hình dạng", "R"), ("Đổi màu", "1–5"), ("Thoát", "Q")]
        for i, (desc, k) in enumerate(keys):
            cell = ctk.CTkFrame(grid, fg_color=FIELD, border_color=LINE, border_width=1, corner_radius=10)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(cell, text=desc, font=self.F.b(13), text_color="#C9CFDB").pack(side="left", padx=12, pady=10)
            caps = ctk.CTkFrame(cell, fg_color="transparent")
            caps.pack(side="right", padx=10)
            for key in ("Ctrl", "Alt", k):
                ctk.CTkLabel(caps, text=key, font=self.F.m(11), text_color=TEXT, fg_color="#181C26",
                             corner_radius=6, width=10, height=24).pack(side="left", padx=2)
        return page

    # ------------------------------------------------------------ Điều hướng & trạng thái
    def show_tab(self, key):
        self.tab = key
        for k, page in self.pages.items():
            if k == key:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        for k, (b, icons) in self.nav_buttons.items():
            if k == key:
                b.configure(fg_color=mix(SIDEBAR, ACCENT, 0.14), hover_color=mix(SIDEBAR, ACCENT, 0.2),
                            border_color=ACCENT, text_color="#FFFFFF", image=icons[0])
            else:
                b.configure(fg_color="transparent", hover_color="#161A23", border_color=SIDEBAR,
                            text_color=TEXT2, image=icons[1])
        if key == "apps":
            self.refresh_apps()

    def update_app_set(self):
        self.app_set = {a.lower() for a in self.cfg["apps"]}

    def save(self):
        self.cfg["enabled"] = self.enabled
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def status_info(self):
        if not self.enabled:
            return "●  ĐANG TẮT", MUTED, "Con trỏ gốc đang được dùng."
        if self.active:
            sub = "Áp dụng cho mọi ứng dụng." if self.cfg["all_apps"] else f"Trong game: {self.fg_exe}"
            return "●  ĐANG HOẠT ĐỘNG", GREEN, sub
        if not self.cfg["apps"]:
            return "●  CHƯA CHỌN GAME", AMBER, "Vào tab Ứng dụng để chọn game."
        return "●  ĐANG CHỜ GAME", AMBER, "Chờ: " + ", ".join(self.cfg["apps"])

    def update_status(self, blink=False):
        text, col, sub = self.status_info()
        dot = mix(col, CARD, 0.6) if blink else col
        self.pill.configure(text=f"  {text}  ", text_color=dot if blink else col,
                            fg_color=mix(CARD, col, 0.14))
        self.status_sub.configure(text=sub)

    def preview_color(self):
        if self.cfg["shape"] == "Ảnh tải lên" and self.src_img is not None and not self.cfg["tint_image"]:
            return ACCENT
        return self.cfg["color"]

    def update_preview(self):
        c = self.cfg
        src = self.src_img
        if src is not None and c["tint_image"]:
            src = tint_image(src, c["color"])
        im = render_preview(c["shape"], self.preview_color(), c["size"], src, c["hotspot"])
        self.pimg = ImageTk.PhotoImage(im, master=self.ov)
        self.pcv.itemconfig(self.pimg_id, image=self.pimg)
        self.pcv.itemconfig(self.size_txt, text=f"{c['size']} PX")

    def update_controls(self):
        c = self.cfg
        for shape, b in self.shape_buttons.items():
            if shape == c["shape"]:
                b.configure(fg_color=mix(CARD, ACCENT, 0.16), hover_color=mix(CARD, ACCENT, 0.24),
                            border_color=ACCENT, text_color="#FFFFFF")
            else:
                b.configure(fg_color=FIELD, hover_color="#161A23", border_color=BORDER, text_color=TEXT2)
        for col, b in self.swatch_buttons.items():
            on = col.lower() == c["color"].lower()
            b.configure(border_width=3 if on else 0, border_color="#FFFFFF")
        custom = c["color"].lower() not in {x.lower() for x, _ in SWATCHES}
        if custom:
            self.custom_btn.configure(fg_color=c["color"], hover_color=c["color"], border_width=3,
                                      border_color="#FFFFFF", image=None)
        else:
            self.custom_btn.configure(fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                      border_color="#4A5266",
                                      image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)))
        self.size_label.configure(text=f"{c['size']} px")

    def refresh(self):
        c = self.cfg
        if self.active:
            draw_cursor(self.cv, c["size"], c["shape"], c["color"], self.img_tk, c["hotspot"])
        else:
            self.cv.delete("all")
        self.update_controls()
        self.update_preview()
        self.update_status()
        self.save()

    def compute_active(self):
        if not self.enabled:
            return False
        if self.cfg["all_apps"]:
            return True
        self.fg_exe = foreground_exe()
        return bool(self.app_set) and self.fg_exe.lower() in self.app_set

    def set_active(self, on):
        if on == self.active:
            return
        self.active = on
        show_real_cursor(not (on and self.cfg["hide_real"]))
        c = self.cfg
        if on:
            draw_cursor(self.cv, c["size"], c["shape"], c["color"], self.img_tk, c["hotspot"])
        else:
            self.cv.delete("all")
        self.update_status()

    # ------------------------------------------------------------ Danh sách ứng dụng
    def refresh_apps(self):
        _name_cache.clear()
        running = list_running_apps()
        running_names = {n.lower() for n, _ in running}
        items = [(n, t, True) for n, t in running]
        items += [(n, "(đang không chạy)", False) for n in self.cfg["apps"] if n.lower() not in running_names]
        old = {k: v.get() for k, v in self.app_vars.items()}
        for w in self.app_list.winfo_children():
            w.destroy()
        self.app_vars = {}
        for name, title, running_now in items:
            checked = old.get(name, name.lower() in self.app_set)
            var = tk.BooleanVar(value=checked)
            self.app_vars[name] = var
            self.add_app_row(name, title, running_now, var)

    def add_app_row(self, name, title, running, var):
        row = ctk.CTkFrame(self.app_list, corner_radius=10, border_width=1, height=54)
        row.pack(fill="x", padx=6, pady=3)
        cb = ctk.CTkCheckBox(row, text="", variable=var, width=24, checkbox_width=20, checkbox_height=20,
                             corner_radius=6, border_width=1, fg_color=ACCENT, hover_color=ACCENT,
                             border_color="#4A5266", checkmark_color="#FFFFFF")
        cb.pack(side="left", padx=(12, 6), pady=10)
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        t = title if len(title) <= 50 else title[:47] + "..."
        l1 = ctk.CTkLabel(txt, text=t, font=self.F.b(14, strong=True), text_color=TEXT, height=20, anchor="w")
        l1.pack(anchor="w")
        l2 = ctk.CTkLabel(txt, text=name, font=self.F.m(12), text_color=MUTED, height=16, anchor="w")
        l2.pack(anchor="w")
        badge_col = CYAN_TEXT if running else MUTED
        badge = ctk.CTkLabel(row, text=" ĐANG CHẠY " if running else " KHÔNG CHẠY ", font=self.F.m(10),
                             text_color=badge_col, corner_radius=11, height=22,
                             fg_color=mix(CARD, CYAN, 0.1) if running else "#181C26")
        badge.pack(side="right", padx=12)

        def style(*_):
            on = var.get()
            row.configure(fg_color=mix(CARD, ACCENT, 0.08) if on else CARD,
                          border_color=mix(CARD, ACCENT, 0.6) if on else CARD)

        def flip(_e=None):
            var.set(not var.get())
            style()

        cb.configure(command=style)
        for w in (row, txt, l1, l2, badge):
            w.bind("<Button-1>", flip)
        style()

    def apply_apps(self):
        self.cfg["apps"] = [n for n, v in self.app_vars.items() if v.get()]
        self.update_app_set()
        self.update_applied_label(just_applied=True)
        self.refresh()

    def update_applied_label(self, just_applied=False):
        txt = ("Đang áp dụng cho: " + ", ".join(self.cfg["apps"])) if self.cfg["apps"] else "Chưa chọn ứng dụng nào."
        if just_applied:
            txt = "✓ Đã áp dụng.  " + txt
        self.applied_label.configure(text=txt, text_color=CYAN_TEXT if just_applied else TEXT2)

    def set_all_apps(self):
        self.cfg["all_apps"] = bool(self.all_var.get())
        self.refresh()

    # ------------------------------------------------------------ Hành động
    def on_enabled_switch(self):
        if bool(self.enabled_var.get()) != self.enabled:
            self.toggle()

    def toggle(self):
        self.enabled = not self.enabled
        self.enabled_var.set(self.enabled)
        self.set_active(self.compute_active())
        self.refresh()
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def set_shape(self, shape):
        self.cfg["shape"] = shape
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
        if s == self.cfg["size"]:
            return
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
            self.img_label.configure(text=Path(path).name)
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
        self.ov.after(6 * 3600 * 1000, self.auto_check_update)

    def check_update(self, manual):
        if not update_configured():
            if manual:
                messagebox.showinfo(APP_NAME, "Chưa cấu hình GITHUB_REPO trong mã nguồn.", parent=self.win)
            return
        if self.checking_update:
            return
        self.checking_update = True
        self.upd_label.configure(text="Đang kiểm tra cập nhật...")

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
                self.upd_label.configure(text="Bạn đang dùng phiên bản mới nhất.")
                if manual:
                    messagebox.showinfo(APP_NAME, f"Bạn đang dùng phiên bản mới nhất ({APP_VERSION}).",
                                        parent=self.win)
                return
            self.upd_label.configure(text=f"Có phiên bản mới: {info['version']}", text_color=ACCENT)
            if not manual and info["version"] == self.cfg["skipped_version"]:
                return
            if self.win.state() == "withdrawn":
                self.pending_update = info
                try:
                    self.icon.notify(f"Đã có EzCursor {info['version']}. Mở EzCursor để cập nhật.", APP_NAME)
                except Exception:
                    pass
            else:
                self.show_update_dialog(info, manual)
        elif kind == "update_error":
            self.checking_update = False
            self.upd_label.configure(text="Không kiểm tra được cập nhật.")
            if manual:
                messagebox.showerror(APP_NAME, f"Không kiểm tra được cập nhật.\nHãy kiểm tra kết nối mạng.\n\n{data}",
                                     parent=self.win)
        elif kind == "dl_progress":
            self.dl_bar.set(data / 100)
            self.dl_label.configure(text=f"Đang tải... {data:.0f}%")
        elif kind == "dl_done":
            self.dl_label.configure(text="Đang cài đặt, EzCursor sẽ tự mở lại sau giây lát...")
            try:
                subprocess.Popen([data, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH"])
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Không chạy được bộ cài:\n{e}", parent=self.upd_dialog)
                return
            self.ov.after(500, self.quit)
        elif kind == "dl_error":
            self.btn_update.configure(state="normal")
            self.dl_label.configure(text="Tải về thất bại.")
            messagebox.showerror(APP_NAME, f"Tải bản cập nhật thất bại:\n{data}", parent=self.upd_dialog)

    def show_update_dialog(self, info, manual):
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        d.title(f"{APP_NAME} - Cập nhật")
        d.resizable(False, False)
        d.attributes("-topmost", True)
        ico = res_path("ezcursor.ico")
        if ico.exists():
            d.after(260, lambda: d.iconbitmap(str(ico)))
        self.upd_dialog = d
        frm = ctk.CTkFrame(d, fg_color="transparent")
        frm.pack(fill="both", padx=20, pady=18)
        self.caps(frm, "CÓ PHIÊN BẢN MỚI", CYAN).pack(anchor="w")
        title = ctk.CTkFrame(frm, fg_color="transparent")
        title.pack(anchor="w", pady=(2, 10))
        ctk.CTkLabel(title, text="EZCURSOR ", font=self.F.h(22), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(title, text=info["version"], font=self.F.h(22), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(title, text=f"   (bạn đang dùng {APP_VERSION})", font=self.F.b(12),
                     text_color=TEXT2).pack(side="left")
        self.caps(frm, "CÓ GÌ MỚI").pack(anchor="w")
        tb = ctk.CTkTextbox(frm, width=520, height=200, fg_color=CARD, border_color=BORDER, border_width=1,
                            corner_radius=10, font=self.F.b(13), text_color=TEXT, wrap="word")
        tb.insert("1.0", info["notes"].strip() or "(không có ghi chú)")
        tb.configure(state="disabled")
        tb.pack(fill="x", pady=(6, 12))
        self.dl_bar = ctk.CTkProgressBar(frm, progress_color=ACCENT, fg_color="#1A1E29", height=8)
        self.dl_bar.set(0)
        self.dl_bar.pack(fill="x")
        self.dl_label = ctk.CTkLabel(frm, text="", font=self.F.b(12), text_color=TEXT2)
        self.dl_label.pack(anchor="w")
        bf = ctk.CTkFrame(frm, fg_color="transparent")
        bf.pack(fill="x", pady=(8, 0))
        if info["url"]:
            self.btn_update = ctk.CTkButton(bf, text="CẬP NHẬT NGAY", command=lambda: self.start_download(info),
                                            height=42, corner_radius=10, fg_color=ACCENT,
                                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        else:
            self.btn_update = ctk.CTkButton(bf, text="MỞ TRANG TẢI VỀ", command=lambda: webbrowser.open(info["page"]),
                                            height=42, corner_radius=10, fg_color=ACCENT,
                                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        self.btn_update.pack(side="right")
        ctk.CTkButton(bf, text="Để sau", command=d.destroy, height=42, width=90, corner_radius=10,
                      fg_color="transparent", hover_color="#161A23", border_width=1, border_color=BORDER,
                      text_color=TEXT2, font=self.F.b(13, strong=True)).pack(side="right", padx=8)
        if not manual:
            def skip():
                self.cfg["skipped_version"] = info["version"]
                self.save()
                d.destroy()
            ctk.CTkButton(bf, text="Bỏ qua phiên bản này", command=skip, height=42, corner_radius=10,
                          fg_color="transparent", hover_color="#161A23", text_color=MUTED,
                          font=self.F.b(12)).pack(side="left")
        d.after(100, d.lift)
        d.after(150, d.focus_force)

    def start_download(self, info):
        self.btn_update.configure(state="disabled")
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
    def anim(self):
        """Hiệu ứng khung xem trước và đèn trạng thái (chỉ chạy khi cửa sổ đang mở)."""
        try:
            visible = self.win.state() != "withdrawn"
        except tk.TclError:
            return
        if visible:
            self.anim_frame += 1
            f = self.anim_frame
            if self.tab == "cursor":
                y = (f * 2 * self.sc) % self.ph
                self.pcv.coords(self.scan, 0, y, self.pw, y)
                phase = (f % 66) / 66
                r = (self.cfg["size"] / 2 + 20) * (0.5 + 1.2 * phase)
                cx, cy = self.pw / 2, self.ph / 2
                self.pcv.coords(self.ping, cx - r, cy - r, cx + r, cy + r)
                self.pcv.itemconfig(self.ping, outline=mix(self.preview_color(), FIELD, min(1, phase * 1.05)))
                if f % 3 == 0:
                    pt = wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    self.pcv.itemconfig(self.coord_txt, text=f"X {pt.x} · Y {pt.y}")
            if f % 24 == 0:
                self.update_status(blink=(f // 24) % 2 == 1 and self.active)
        self.ov.after(33, self.anim)

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
                self.show_tab("opts")
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
        if self.tick_count % 25 == 0:
            for flag, action in ((SHOW_FLAG, self.show_window), (QUIT_FLAG, self.quit)):
                if flag.exists():
                    try:
                        flag.unlink()
                    except OSError:
                        pass
                    action()
                    if flag is QUIT_FLAG:
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
    if "--quit" in sys.argv:
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

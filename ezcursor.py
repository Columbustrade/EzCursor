# -*- coding: utf-8 -*-
"""
EzCursor - con trỏ chuột tùy chỉnh cho game có con trỏ riêng (vd: Last Epoch)

- Giao diện Neon HUD (CustomTkinter)
- Tab "Ứng dụng": chọn ứng dụng đang chạy để áp dụng con trỏ, bấm Áp dụng
- Giao diện tiếng Việt / tiếng Anh (tab Tùy chọn > Ngôn ngữ)
- Bấm X: thu nhỏ xuống khay hệ thống. Thoát hẳn: menu khay hoặc Ctrl+Alt+Q
Phím tắt: Ctrl+Alt+H bật/tắt, Ctrl+Alt+R đổi hình, Ctrl+Alt+1..5 đổi màu, Ctrl+Alt+Q thoát
Cài đặt lưu tại %APPDATA%\\EzCursor
"""

import atexit
import colorsys
import ctypes
import json
import math
import os
import random
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
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

APP_NAME = "EzCursor"
APP_VERSION = "1.3.0"

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
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
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
SHAPES = ["EzDrop", "EzPink", "Mũi tên", "Vòng tròn", "Dấu thập", "Chấm tròn", "Kim cương", "Ảnh tải lên", "Bibata"]
HOTSPOTS = ["Giữa ảnh", "Góc trên trái"]
ARROW_TIP = 3
PREVIEW = 170

DEFAULT_CFG = {
    "color": PRESET_COLORS[0],
    "shape": "EzDrop",
    "size": 64,
    "image": "",
    "hotspot": HOTSPOTS[0],
    "tint_image": True,
    "glow": True,
    "cursor_sparkle": False,
    "splash": True,
    "fx_trail": "off",
    "fx_click": "off",
    "fx_color": "cursor",
    "fx_density": "mid",
    "bibata_cursor": "left_ptr",
    "bibata_theme": "amber",
    "bibata_style": "modern",
    "bibata_hand": "right",
    "hide_real": True,
    "enabled": True,
    "all_apps": False,
    "apps": [],
    "tray_hint_shown": False,
    "auto_check_update": True,
    "last_update_check": 0,
    "skipped_version": "",
    "language": "vi",
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
    if cfg["bibata_theme"] not in ("amber", "classic", "ice", "custom"):
        cfg["bibata_theme"] = "amber"
    if cfg["bibata_style"] not in ("modern", "original"):
        cfg["bibata_style"] = "modern"
    if cfg["bibata_hand"] not in ("right", "left"):
        cfg["bibata_hand"] = "right"
    if cfg["fx_trail"] not in ("off", "sparkle", "neon", "rainbow", "ghost", "bubble"):
        cfg["fx_trail"] = "off"
    if cfg["fx_click"] not in ("off", "ripple", "burst"):
        cfg["fx_click"] = "off"
    if cfg["fx_color"] not in ("cursor", "ez"):
        cfg["fx_color"] = "cursor"
    if cfg["fx_density"] not in ("low", "mid", "high"):
        cfg["fx_density"] = "mid"
    if cfg["language"] not in dict(LANGUAGES):
        cfg["language"] = "vi"
    if not isinstance(cfg["apps"], list):
        cfg["apps"] = list(DEFAULT_CFG["apps"])
    if cfg["image"] and not Path(cfg["image"]).exists():
        alt = APP_DIR / Path(cfg["image"]).name
        cfg["image"] = str(alt) if alt.exists() else ""
    return cfg


# ---------------------------------------------------------------- Ngôn ngữ giao diện
LANGUAGES = [("vi", "Tiếng Việt"), ("en", "English")]
LANG = "vi"          # đổi qua App.set_language
# Bảng dịch Việt -> Anh. Chuỗi tiếng Việt là khóa; thiếu khóa thì giữ nguyên tiếng Việt.
TR_EN = {
    # Thanh bên & khay hệ thống
    "Con trỏ": "Cursor", "Bộ sưu tập": "Library", "Hiệu ứng": "Effects", "Ứng dụng": "Apps",
    "Tùy chọn": "Options", "TRẠNG THÁI": "STATUS", "Bật EzCursor": "Enable EzCursor",
    "Mở EzCursor": "Open EzCursor", "Bật con trỏ": "Enable cursor", "Kiểm tra cập nhật": "Check for updates",
    "Thoát": "Quit",
    # Tab Con trỏ
    "CON TRỎ": "CURSOR",
    "Chọn hình dạng, màu sắc và kích thước con trỏ trong game.": "Choose the shape, color and size of your in-game cursor.",
    "XEM TRƯỚC": "PREVIEW", "HÌNH DẠNG": "SHAPE", "MÀU SẮC": "COLOR", "KÍCH THƯỚC": "SIZE",
    "ẢNH TÙY CHỈNH": "CUSTOM IMAGE", "Tải ảnh lên": "Upload image", "(chưa có ảnh)": "(no image)",
    "Điểm click": "Click point", "Giữa ảnh": "Center", "Góc trên trái": "Top-left",
    "Tô màu cho ảnh tải lên": "Tint uploaded image", "Quầng sáng quanh con trỏ": "Glow around cursor",
    "Mũi tên": "Arrow", "Vòng tròn": "Circle", "Dấu thập": "Cross", "Chấm tròn": "Dot",
    "Kim cương": "Diamond", "Ảnh": "Image",
    # Tab Bộ sưu tập
    "BỘ SƯU TẬP": "LIBRARY",
    "Con trỏ của EzCursor và bộ Bibata. Bấm vào con trỏ muốn dùng.": "EzCursor's own cursors and the Bibata set. Click a cursor to use it.",
    "Không tìm thấy thư mục bibata đi kèm phần mềm.": "The bundled bibata folder was not found.",
    "CHỦ ĐỀ": "THEME", "Tùy chỉnh": "Custom", "MÀU TÙY CHỈNH": "CUSTOM COLOR",
    "Modern · bo tròn": "Modern · rounded", "Original · góc nhọn": "Original · sharp",
    "Thuận tay phải": "Right-handed", "Thuận tay trái": "Left-handed",
    "Chọn một màu để chuyển sang chủ đề Tùy chỉnh.": "Pick a color to switch to the Custom theme.",
    "Chọn màu": "Choose color", "Mảnh hồng": "Pink Shard",
    "Mũi tên ngược": "Reverse arrow", "Mũi tên đứng": "Upright arrow", "Bàn tay chỉ": "Pointing hand",
    "Bàn tay mở": "Open hand", "Nắm tay": "Grabbing", "Tâm ngắm": "Crosshair", "Thập mảnh": "Thin cross",
    "Dấu cộng": "Plus", "Ô chấm": "Dot box", "Dấu X": "X", "Bút chì": "Pencil",
    # Tab Hiệu ứng
    "HIỆU ỨNG": "EFFECTS",
    "Thêm vệt sáng theo con trỏ và hiệu ứng khi click trong game.": "Add a glowing trail behind the cursor and click effects in game.",
    "VỆT THEO CON TRỎ": "CURSOR TRAIL", "KHI CLICK CHUỘT TRÁI": "ON LEFT CLICK", "QUANH CON TRỎ": "AROUND CURSOR",
    "Tắt": "Off", "Lấp lánh": "Sparkle", "Vệt neon": "Neon trail", "Cầu vồng": "Rainbow",
    "Bóng mờ": "Ghost", "Bong bóng": "Bubbles", "Gợn sóng": "Ripple", "Pháo hoa": "Fireworks",
    "Theo màu con trỏ": "Match cursor color", "Ba màu EzCursor": "EzCursor tri-color",
    "Ít": "Low", "Vừa": "Medium", "Nhiều": "High", "Màu hiệu ứng": "Effect color", "Mật độ": "Density",
    "THỬ NGAY TRÊN MÀN HÌNH": "TRY IT ON SCREEN", "ĐANG THỬ...": "TESTING...",
    "   Di chuột và click trong 8 giây để xem hiệu ứng.": "   Move and click the mouse for 8 seconds to see the effects.",
    "Hãy chọn ít nhất một hiệu ứng trước khi thử.": "Please select at least one effect before testing.",
    # Tab Ứng dụng
    "ỨNG DỤNG": "APPS",
    "Chọn game sẽ dùng con trỏ của EzCursor, rồi bấm Áp dụng.": "Select the games that will use the EzCursor cursor, then click Apply.",
    "Làm mới": "Refresh", "  Áp dụng cho mọi ứng dụng (kể cả Desktop)": "  Apply to all apps (including Desktop)",
    "ÁP DỤNG": "APPLY", "(đang không chạy)": "(not running)", " ĐANG CHẠY ": " RUNNING ",
    " KHÔNG CHẠY ": " NOT RUNNING ", "Đang áp dụng cho: ": "Applied to: ",
    "Chưa chọn ứng dụng nào.": "No apps selected.", "✓ Đã áp dụng.  ": "✓ Applied.  ",
    # Tab Tùy chọn
    "TÙY CHỌN": "OPTIONS", "Cài đặt chung, cập nhật và phím tắt.": "General settings, updates and hotkeys.",
    "Ngôn ngữ": "Language", "Ngôn ngữ hiển thị của EzCursor.": "Display language of EzCursor.",
    "Ẩn con trỏ thật của game": "Hide the game's real cursor",
    "Chỉ hiện con trỏ của EzCursor khi đang ở trong game.": "Show only the EzCursor cursor while in game.",
    "Khởi động cùng Windows": "Start with Windows",
    "Chạy ngầm dưới khay hệ thống khi bật máy.": "Run in the system tray when your PC starts.",
    "Tự động kiểm tra cập nhật": "Check for updates automatically",
    "Thông báo khi có phiên bản mới trên GitHub.": "Notify when a new version is on GitHub.",
    "Màn hình chào khi mở": "Splash screen on launch",
    "Hiện logo động khoảng 2 giây mỗi lần mở EzCursor.": "Show the animated logo for about 2 seconds at launch.",
    "Phiên bản ": "Version ", "Khôi phục cài đặt gốc": "Reset to defaults",
    "Xóa mọi lựa chọn đã lưu và khởi động lại EzCursor như mới cài.": "Clear all saved settings and restart EzCursor as freshly installed.",
    "Khôi phục": "Reset", "PHÍM TẮT": "HOTKEYS", "Bật / tắt": "On / off", "Đổi hình dạng": "Change shape",
    "Đổi màu": "Change color",
    # Trạng thái
    "●  ĐANG TẮT": "●  OFF", "Con trỏ gốc đang được dùng.": "The default cursor is in use.",
    "Áp dụng cho mọi ứng dụng.": "Applied to all apps.", "Trong game: ": "In game: ",
    "●  ĐANG HOẠT ĐỘNG": "●  ACTIVE", "●  TẠM DỪNG": "●  PAUSED",
    "Đang ở trên giao diện của Windows.": "Over a Windows interface.",
    "●  CHƯA CHỌN GAME": "●  NO GAME SELECTED", "Vào tab Ứng dụng để chọn game.": "Go to the Apps tab to pick a game.",
    "●  ĐANG CHỜ GAME": "●  WAITING FOR GAME", "Chờ: ": "Waiting: ",
    # Hộp thoại & thông báo
    "Lỗi": "Error", "Không thay đổi được cài đặt khởi động:": "Could not change the startup setting:",
    "Chọn ảnh con trỏ": "Choose a cursor image", "Tất cả": "All files",
    "Không sao chép được ảnh:": "Could not copy the image:", "Không mở được ảnh:": "Could not open the image:",
    "EzCursor vẫn đang chạy dưới khay hệ thống. Chuột phải vào icon để mở lại hoặc thoát.":
        "EzCursor is still running in the system tray. Right-click the icon to reopen or quit.",
    "Khôi phục toàn bộ cài đặt về mặc định?\n\nDanh sách game, con trỏ, hiệu ứng và ảnh đã tải lên sẽ bị xóa. EzCursor sẽ tự khởi động lại.":
        "Reset all settings to defaults?\n\nYour game list, cursor, effects and uploaded image will be removed. EzCursor will restart automatically.",
    "Chưa cấu hình GITHUB_REPO trong mã nguồn.": "GITHUB_REPO is not configured in the source code.",
    "Đang kiểm tra cập nhật...": "Checking for updates...",
    "Bạn đang dùng phiên bản mới nhất.": "You are using the latest version.",
    "Bạn đang dùng phiên bản mới nhất": "You are using the latest version",
    "Có phiên bản mới: ": "New version available: ",
    "Đã có EzCursor {v}. Mở EzCursor để cập nhật.": "EzCursor {v} is available. Open EzCursor to update.",
    "Không kiểm tra được cập nhật.": "Could not check for updates.",
    "Không kiểm tra được cập nhật.\nHãy kiểm tra kết nối mạng.": "Could not check for updates.\nPlease check your internet connection.",
    "Đang tải...": "Downloading...",
    "Đang cài đặt, EzCursor sẽ tự mở lại sau giây lát...": "Installing, EzCursor will reopen in a moment...",
    "Không chạy được bộ cài:": "Could not run the installer:", "Tải về thất bại.": "Download failed.",
    "Tải bản cập nhật thất bại:": "Failed to download the update:", "Cập nhật": "Update",
    "CÓ PHIÊN BẢN MỚI": "NEW VERSION AVAILABLE", "   (bạn đang dùng {v})": "   (you have {v})",
    "CÓ GÌ MỚI": "WHAT'S NEW", "(không có ghi chú)": "(no release notes)", "CẬP NHẬT NGAY": "UPDATE NOW",
    "MỞ TRANG TẢI VỀ": "OPEN DOWNLOAD PAGE", "Để sau": "Later", "Bỏ qua phiên bản này": "Skip this version",
}


def T(text):
    """Dịch chuỗi giao diện sang ngôn ngữ đang chọn (mặc định tiếng Việt)."""
    if LANG == "en":
        return TR_EN.get(text, text)
    return text


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
    try:
        return Image.open(res_path("logo.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
    except Exception:
        pass
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
        s = s * size / 20          # icon thiết kế trên lưới 20 đơn vị
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
        elif kind == "fx":
            c = 10 * s
            r = 8.5 * s
            d.polygon([(c + x * r, c + y * r) for x, y in STAR_PTS], outline=color, width=int(1.8 * s))
            d.ellipse([15 * s, 2 * s, 18.4 * s, 5.4 * s], fill=color)
        elif kind == "library":
            for x0, y0 in ((3, 3), (11, 3), (3, 11), (11, 11)):
                d.rounded_rectangle([x0 * s, y0 * s, (x0 + 6) * s, (y0 + 6) * s], radius=1.6 * s,
                                    outline=color, width=w)
        else:  # tùy chọn
            d.line([(3 * s, 6 * s), (17 * s, 6 * s)], fill=color, width=w)
            d.line([(3 * s, 14 * s), (17 * s, 14 * s)], fill=color, width=w)
            for cx, cy in ((7.5 * s, 6 * s), (12.5 * s, 14 * s)):
                d.ellipse([cx - 2.4 * s, cy - 2.4 * s, cx + 2.4 * s, cy + 2.4 * s], fill=SIDEBAR, outline=color, width=w)
    return _ss(draw, size)


_logo_frames = None


def logo_frames():
    """Danh sách khung hình logo động (ảnh vuông) từ assets/logo_anim.png."""
    global _logo_frames
    if _logo_frames is None:
        try:
            sheet = Image.open(res_path("assets", "logo_anim.png")).convert("RGBA")
            f = sheet.height
            _logo_frames = [sheet.crop((i * f, 0, (i + 1) * f, f)) for i in range(sheet.width // f)]
        except Exception:
            _logo_frames = []
    return _logo_frames


def logo_image(size=26):
    try:
        return Image.open(res_path("logo.png")).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        pass
    def draw(d, s):
        pts = [(2 * s, 1.5 * s), (24 * s, 13 * s), (24 * s, 24 * s), (13 * s, 24 * s)]
        d.polygon(pts, fill=ACCENT)
        d.line(pts + [pts[0]], fill="#FFFFFF", width=int(2.2 * s), joint="curve")
    return _ss(draw, size)


def simple_icon(kind, color, size=16):
    def draw(d, s):
        s = s * size / 16          # icon thiết kế trên lưới 16 đơn vị
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


def render_shape(shape, color, size, img_rgba, hotspot):
    """Vẽ con trỏ (khử răng cưa), trả về (ảnh RGBA, điểm click)."""
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
    if shape == "Mũi tên":
        hot = (round(3 * size / 64), round(3 * size / 64))
    elif shape == "Ảnh tải lên" and hotspot == "Góc trên trái":
        hot = (0, 0)
    else:
        hot = (size // 2, size // 2)
    return im, hot


# ---------------------------------------------------------------- Bộ con trỏ Bibata
BIBATA_THEMES = {
    "amber": ("Amber", "#FF8300", "#FFFFFF", "#001524"),
    "classic": ("Classic", "#000000", "#FFFFFF", "#000000"),
    "ice": ("Ice", "#FFFFFF", "#000000", "#FFFFFF"),
}
BIBATA_CURSORS = [
    ("left_ptr", "Mũi tên"), ("right_ptr", "Mũi tên ngược"), ("center_ptr", "Mũi tên đứng"),
    ("hand2", "Bàn tay chỉ"), ("hand1", "Bàn tay mở"), ("grabbing", "Nắm tay"),
    ("crosshair", "Tâm ngắm"), ("cross", "Dấu thập"), ("tcross", "Thập mảnh"),
    ("plus", "Dấu cộng"), ("dotbox", "Ô chấm"), ("X_cursor", "Dấu X"), ("pencil", "Bút chì"),
]


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def luminance(c):
    r, g, b = _rgb(c)
    return 0.299 * r + 0.587 * g + 0.114 * b


def bibata_colors(theme, custom_color):
    if theme in BIBATA_THEMES:
        return BIBATA_THEMES[theme][1:]
    outline = "#000000" if luminance(custom_color) > 170 else "#FFFFFF"
    return custom_color, outline, "#001524" if outline == "#FFFFFF" else "#FFFFFF"


_bib_cache = {}


def bibata_image(base_dir, variant, name, colors):
    """Ảnh con trỏ Bibata 256px đã tô màu (thân, viền, phụ)."""
    key = (variant, name, colors)
    if key in _bib_cache:
        return _bib_cache[key]
    src = Image.open(base_dir / variant / f"{name}.png").convert("RGBA")
    r, g, b, a = src.split()
    base, outline, accent = (_rgb(c) for c in colors)
    chans = []
    for k in range(3):
        layer = ImageChops.add(ImageChops.add(g.point(lambda v, f=base[k]: v * f // 255),
                                              b.point(lambda v, f=outline[k]: v * f // 255)),
                               r.point(lambda v, f=accent[k]: v * f // 255))
        chans.append(layer)
    out = Image.merge("RGBA", (*chans, a))
    fixed = base_dir / variant / f"{name}.fixed.png"
    if fixed.exists():
        out.alpha_composite(Image.open(fixed).convert("RGBA"))
    if len(_bib_cache) > 64:
        _bib_cache.clear()
    _bib_cache[key] = out
    return out


BIBATA_DIR = res_path("bibata")
# Con trỏ riêng của EzCursor: (mã hình, tên hiển thị, file ảnh 256 px, điểm click, màu quầng sáng)
OWN_CURSORS = [
    ("EzDrop", "Liquid Drop", "ezdrop.png", (21, 20), "#FF2E93"),
    ("EzPink", "Mảnh hồng", "ezpink.png", (25,21), "#FF2E93"),
]
OWN_BY_ID = {c[0]: c for c in OWN_CURSORS}
_own_imgs = {}


def own_image(shape):
    if shape not in OWN_BY_ID:
        return None
    if shape not in _own_imgs:
        try:
            _own_imgs[shape] = Image.open(res_path("assets", OWN_BY_ID[shape][2])).convert("RGBA")
        except Exception:
            _own_imgs[shape] = None
    return _own_imgs[shape]


def ezdrop_image():
    return own_image("EzDrop")
try:
    BIBATA_META = json.loads((BIBATA_DIR / "bibata.json").read_text(encoding="utf-8"))
except Exception:
    BIBATA_META = {"hotspots": {}}


# ---------------------------------------------------------------- Overlay trong suốt từng điểm ảnh
gdi32 = ctypes.windll.gdi32
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HANDLE), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HANDLE)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, ctypes.c_void_p]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       wintypes.DWORD, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HANDLE
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


@WNDPROC
def _overlay_wndproc(hwnd, msg, wparam, lparam):
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


class LayeredOverlay:
    """Cửa sổ con trỏ: trong suốt từng điểm ảnh, click xuyên qua, luôn trên cùng."""

    def __init__(self):
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = _overlay_wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "EzCursorOverlay"
        user32.RegisterClassExW(ctypes.byref(wc))
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | 0x8  # WS_EX_TOPMOST
        self.hwnd = user32.CreateWindowExW(ex, "EzCursorOverlay", "EzCursor Overlay", 0x80000000,
                                           0, 0, 1, 1, None, None, hinst, None)
        self.visible = False

    def set_image(self, im, pos=None):
        w, h = im.size
        r, g, b, a = im.convert("RGBa").split()          # RGBa = đã nhân alpha sẵn
        data = Image.merge("RGBA", (b, g, r, a)).tobytes()
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, data, len(data))
        old = gdi32.SelectObject(mem, hbmp)
        size = wintypes.SIZE(w, h)
        src = wintypes.POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)
        dst = ctypes.byref(wintypes.POINT(int(pos[0]), int(pos[1]))) if pos else None
        user32.UpdateLayeredWindow(self.hwnd, screen, dst, ctypes.byref(size), mem, ctypes.byref(src),
                                   0, ctypes.byref(blend), 2)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)

    def move(self, x, y):
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)

    def show(self, on):
        if on != self.visible:
            user32.ShowWindow(self.hwnd, 4 if on else 0)    # SW_SHOWNOACTIVATE / SW_HIDE
            self.visible = on

    def destroy(self):
        try:
            user32.DestroyWindow(self.hwnd)
        except Exception:
            pass


# Các bảng giao diện của Windows nằm trên lớp "luôn trên cùng" -> tạm hiện con trỏ thật
SHELL_UI_EXES = {"startmenuexperiencehost.exe", "searchhost.exe", "searchapp.exe", "searchui.exe",
                 "shellexperiencehost.exe", "lockapp.exe"}
SHELL_UI_CLASSES = {"XamlExplorerHostIslandWindow", "MultitaskingViewFrame", "TaskSwitcherWnd",
                    "ForegroundStaging", "Windows.UI.Core.CoreWindow"}


user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
# Cửa sổ của explorer.exe dưới con trỏ vẫn dùng con trỏ tùy chỉnh nếu là desktop hoặc thư mục
SHELL_HOVER_OK = {"Progman", "WorkerW", "CabinetWClass", "ExploreWClass", "EzCursorOverlay"}


def class_name(h):
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(h, buf, 128)
    return buf.value


def shell_ui_open():
    """True khi giao diện riêng của Windows (Start, Search, taskbar, xem trước...) đang mở hoặc ở dưới chuột."""
    h = user32.GetForegroundWindow()
    if h:
        exe = exe_name(pid_of(h)).lower()
        if exe in SHELL_UI_EXES:
            return True
        if exe in ("explorer.exe", "") and class_name(h) in SHELL_UI_CLASSES:
            return True
    # Cửa sổ ngay dưới con trỏ: khung xem trước taskbar, khay hệ thống, thông báo... không lấy focus
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    under = user32.WindowFromPoint(pt)
    if under:
        root = user32.GetAncestor(under, 2) or under          # GA_ROOT
        if class_name(root) not in SHELL_HOVER_OK:
            exe = exe_name(pid_of(root)).lower()
            if exe in SHELL_UI_EXES or exe == "explorer.exe":
                return True
    return False


def add_glow(im, hot, color):
    """Thêm quầng sáng quanh con trỏ, trả về ảnh mới và điểm click mới."""
    size = max(im.size)
    pad = max(10, size // 3)
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    alpha = Image.new("L", out.size, 0)
    alpha.paste(im.getchannel("A"), (pad, pad))
    alpha = alpha.filter(ImageFilter.GaussianBlur(max(4, size / 9))).point(lambda v: int(v * 0.85))
    glow = Image.new("RGBA", out.size, color)
    glow.putalpha(alpha)
    out.alpha_composite(glow)
    out.alpha_composite(im, (pad, pad))
    return out, (hot[0] + pad, hot[1] + pad)


# ---------------------------------------------------------------- Hiệu ứng theo con trỏ
FX_TRAILS = [("off", "Tắt"), ("sparkle", "Lấp lánh"), ("neon", "Vệt neon"),
             ("rainbow", "Cầu vồng"), ("ghost", "Bóng mờ"), ("bubble", "Bong bóng")]
FX_CLICKS = [("off", "Tắt"), ("ripple", "Gợn sóng"), ("burst", "Pháo hoa")]
EZ_COLORS = ["#2EE59D", "#2F80FF", "#FF2E93"]
FX_DENSITY = {"low": 0.5, "mid": 1.0, "high": 2.0}
FX_BOX = 600          # kích thước tối đa của lớp hiệu ứng quanh con trỏ
VK_LBUTTON = 0x01
STAR_PTS = [(0, -1), (0.14, -0.29), (0.29, -0.14), (1, 0), (0.29, 0.14), (0.14, 0.29),
            (0, 1), (-0.14, 0.29), (-0.29, 0.14), (-1, 0), (-0.29, -0.14), (-0.14, -0.29)]


def hue_color(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 0.75, 1.0)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def star_sprite(color, size):
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = n / 2
    r = n * 0.36
    d.polygon([(c + x * r, c + y * r) for x, y in STAR_PTS], fill=color)
    d.ellipse([c - r * 0.12, c - r * 0.12, c + r * 0.12, c + r * 0.12], fill="#FFFFFF")
    im = im.resize((size, size), Image.LANCZOS)
    glow = Image.new("RGBA", im.size, color)
    glow.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(size / 7)).point(lambda v: int(v * 0.8)))
    glow.alpha_composite(im)
    return glow


def soft_dot(color, size, hard=0.45):
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = n / 2
    d.ellipse([c - n * 0.22, c - n * 0.22, c + n * 0.22, c + n * 0.22], fill=color)
    im = im.filter(ImageFilter.GaussianBlur(n * 0.08))
    core = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(core).ellipse([c - n * 0.22 * hard, c - n * 0.22 * hard, c + n * 0.22 * hard, c + n * 0.22 * hard],
                                 fill=mix(color, "#FFFFFF", 0.55))
    im.alpha_composite(core.filter(ImageFilter.GaussianBlur(n * 0.03)))
    return im.resize((size, size), Image.LANCZOS)


def bubble_sprite(color, size):
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, n // 12)
    d.ellipse([w, w, n - w, n - w], outline=color, width=w)
    d.ellipse([n * 0.28, n * 0.24, n * 0.42, n * 0.38], fill="#FFFFFF")
    return im.resize((size, size), Image.LANCZOS)


class FxEngine:
    """Hệ hạt cho hiệu ứng vệt chuột và click, vẽ ra một ảnh RGBA quanh con trỏ."""

    def __init__(self):
        self.parts = []      # [x, y, vx, vy, age, life, sprite_key, gravity]
        self.trail = []      # [(x, y, t)]
        self.ghosts = []     # [(x, y, t)]
        self.rings = []      # [x, y, age, color]
        self.cache = {}
        self.last = None
        self.dist = 0.0
        self.hue = 0.0
        self.last_ghost = 0.0
        self.ghost_img = None

    def sprite(self, kind, color, size):
        key = (kind, color, size)
        im = self.cache.get(key)
        if im is None:
            if len(self.cache) > 400:
                self.cache.clear()
            im = {"star": star_sprite, "dot": soft_dot, "bubble": bubble_sprite}[kind](color, size)
            self.cache[key] = im
        return im

    def faded(self, key, im, alpha):
        q = max(0, min(8, round(alpha * 8)))
        if q == 0:
            return None
        if q == 8:
            return im
        k = ("fade", key, q)
        out = self.cache.get(k)
        if out is None:
            out = im.copy()
            out.putalpha(im.getchannel("A").point(lambda v, f=q / 8: int(v * f)))
            self.cache[k] = out
        return out

    def busy(self):
        return bool(self.parts or self.trail or self.ghosts or self.rings)

    def clear(self):
        self.parts.clear(); self.trail.clear(); self.ghosts.clear(); self.rings.clear()
        self.last = None

    def update(self, now, dt, pos, clicked, cfg, palette, ghost_img):
        trail = cfg["fx_trail"]
        dens = FX_DENSITY.get(cfg["fx_density"], 1.0)
        x, y = pos
        moved = 0.0
        if self.last is not None:
            moved = math.hypot(x - self.last[0], y - self.last[1])
        self.last = pos
        if moved > 400:          # nhảy chuột quá xa (đổi màn hình...) -> bỏ qua
            moved = 0
            self.trail.clear()
        self.dist += moved
        self.hue = (self.hue + dt * 0.6) % 1.0

        if trail in ("sparkle", "bubble"):
            step = (14 if trail == "sparkle" else 22) / dens
            while self.dist >= step:
                self.dist -= step
                col = random.choice(palette)
                if trail == "sparkle":
                    size = random.choice((14, 18, 22, 26))
                    self.parts.append([x + random.uniform(-8, 8), y + random.uniform(-8, 8),
                                       random.uniform(-25, 25), random.uniform(5, 40), 0.0,
                                       random.uniform(0.45, 0.8), ("star", col, size), 0.0])
                else:
                    size = random.choice((10, 14, 18))
                    self.parts.append([x + random.uniform(-6, 6), y + random.uniform(-4, 4),
                                       random.uniform(-15, 15), random.uniform(-70, -35), 0.0,
                                       random.uniform(0.7, 1.1), ("bubble", col, size), 0.0])
        else:
            self.dist = 0.0
        if trail in ("neon", "rainbow"):
            if moved > 0.5 or not self.trail:
                self.trail.append((x, y, now))
        if trail == "ghost" and ghost_img is not None:
            self.ghost_img = ghost_img
            if moved > 2 and now - self.last_ghost > 0.03:
                self.ghosts.append((x, y, now))
                self.last_ghost = now
        life_trail = 0.32 * (0.8 + 0.2 * dens)
        self.trail = [p for p in self.trail if now - p[2] < life_trail][-80:]
        self.ghosts = [p for p in self.ghosts if now - p[2] < 0.22][-8:]

        if clicked:
            if cfg["fx_click"] == "ripple":
                self.rings.append([x, y, 0.0, random.choice(palette)])
            elif cfg["fx_click"] == "burst":
                n = int(14 * (0.7 + 0.3 * dens))
                for i in range(n):
                    a = 2 * math.pi * i / n + random.uniform(-0.2, 0.2)
                    sp = random.uniform(140, 300)
                    self.parts.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 0.0,
                                       random.uniform(0.5, 0.8), ("dot", random.choice(palette), 16), 420.0])

        alive = []
        for p in self.parts:
            p[4] += dt
            if p[4] < p[5]:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[3] += p[7] * dt
                alive.append(p)
        self.parts = alive
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.5]

    def render(self, now, cursor, cfg, palette, ghost_hot):
        cx, cy = cursor
        half = FX_BOX // 2
        left, top = int(cx - half), int(cy - half)
        items = []          # (ảnh, x, y)
        for p in self.parts:
            im = self.sprite(*p[6])
            t = p[4] / p[5]
            if p[6][0] == "star":
                a = math.sin(min(1.0, t) * math.pi) ** 0.7
            else:
                a = 1.0 - t
            f = self.faded(p[6], im, a)
            if f is not None:
                items.append((f, p[0] - im.width / 2, p[1] - im.height / 2))
        if self.trail:
            pts = self.trail
            stamps = []
            for i in range(1, len(pts)):
                (x0, y0, _), (x1, y1, t1) = pts[i - 1], pts[i]
                seg = math.hypot(x1 - x0, y1 - y0)
                k = max(1, int(seg / 4))
                for j in range(k):
                    u = j / k
                    stamps.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, t1))
            stamps.append((pts[-1][0], pts[-1][1], pts[-1][2]))
            n = len(stamps)
            for i, (sx, sy, st) in enumerate(stamps):
                frac = (i + 1) / n
                size = 8 + 4 * round(frac * 5)                 # 8..28 px, lượng tử hóa để dùng cache
                if cfg["fx_trail"] == "rainbow":
                    col = hue_color(round((self.hue + frac * 0.6) * 24) / 24)
                else:
                    col = palette[min(len(palette) - 1, int(frac * len(palette)))]
                im = self.sprite("dot", col, size)
                f = self.faded(("dot", col, size), im, 0.25 + 0.75 * frac)
                if f is not None:
                    items.append((f, sx - size / 2, sy - size / 2))
        if self.ghosts and self.ghost_img is not None:
            gi = self.ghost_img
            for (gx, gy, gt) in self.ghosts:
                a = 0.45 * (1 - (now - gt) / 0.22)
                f = self.faded(("ghost", id(gi)), gi, a)
                if f is not None:
                    items.append((f, gx - ghost_hot[0], gy - ghost_hot[1]))

        box = Image.new("RGBA", (FX_BOX, FX_BOX), (0, 0, 0, 0))
        drawn = False
        if self.rings:
            d = ImageDraw.Draw(box)
            for x, y, age, col in self.rings:
                t = age / 0.5
                r = 10 + 60 * (1 - (1 - t) ** 3)
                c = mix(col, "#000000", 0)
                rgb = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
                alpha = int(255 * (1 - t))
                bx, by = x - left, y - top
                if r < bx < FX_BOX - r and r < by < FX_BOX - r:
                    d.ellipse([bx - r, by - r, bx + r, by + r], outline=rgb + (alpha,), width=4)
                    r2 = r * 0.6
                    d.ellipse([bx - r2, by - r2, bx + r2, by + r2], outline=(255, 255, 255, alpha // 2), width=2)
                    drawn = True
        for im, x, y in items:
            ix, iy = int(x - left), int(y - top)
            if 0 <= ix and 0 <= iy and ix + im.width <= FX_BOX and iy + im.height <= FX_BOX:
                box.alpha_composite(im, (ix, iy))
                drawn = True
        if not drawn:
            return None, (left, top)
        bb = box.getbbox()
        if bb is None:
            return None, (left, top)
        return box.crop(bb), (left + bb[0], top + bb[1])


def fx_icon(kind, size=48):
    """Ảnh minh họa nhỏ cho các ô chọn hiệu ứng."""
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    G_, B_, P_ = EZ_COLORS
    if kind == "aura":
        base = [(0, 0), (0, 0.5), (0.13, 0.38), (0.22, 0.58), (0.3, 0.54), (0.21, 0.35), (0.38, 0.35)]
        d.polygon([(n * (0.2 + x), n * (0.28 + y)) for x, y in base], fill=P_)
        for (cx, cy, r, col) in ((0.7, 0.24, 0.13, "#FFFFFF"), (0.8, 0.52, 0.08, G_), (0.18, 0.84, 0.07, B_)):
            d.polygon([(n * cx + x * n * r, n * cy + y * n * r) for x, y in STAR_PTS], fill=col)
    elif kind == "off":
        w = int(3 * S)
        d.ellipse([n * 0.22, n * 0.22, n * 0.78, n * 0.78], outline="#8B93A7", width=w)
        d.line([(n * 0.32, n * 0.68), (n * 0.68, n * 0.32)], fill="#8B93A7", width=w)
    elif kind == "sparkle":
        for (cx, cy, r, col) in ((0.32, 0.36, 0.2, "#FFFFFF"), (0.66, 0.6, 0.15, P_), (0.66, 0.24, 0.09, G_), (0.3, 0.74, 0.08, B_)):
            d.polygon([(n * cx + x * n * r, n * cy + y * n * r) for x, y in STAR_PTS], fill=col)
    elif kind in ("neon", "rainbow"):
        pts = [(0.15 + 0.7 * i / 30, 0.62 - 0.28 * math.sin(i / 30 * math.pi * 1.4)) for i in range(31)]
        for i, (x, y) in enumerate(pts):
            f = i / 30
            col = hue_color(f * 0.8) if kind == "rainbow" else [G_, B_, P_][min(2, int(f * 3))]
            r = n * (0.02 + 0.05 * f)
            d.ellipse([n * x - r, n * y - r, n * x + r, n * y + r], fill=col)
    elif kind == "ghost":
        base = [(0, 0), (0, 0.5), (0.13, 0.38), (0.22, 0.58), (0.3, 0.54), (0.21, 0.35), (0.38, 0.35)]
        for k, (ox, a) in enumerate(((0.1, 70), (0.25, 140), (0.42, 255))):
            col = tuple(int(P_[i:i + 2], 16) for i in (1, 3, 5)) + (a,)
            d.polygon([(n * (ox + x), n * (0.22 + y)) for x, y in base], fill=col)
    elif kind == "bubble":
        for (cx, cy, r, col) in ((0.36, 0.62, 0.17, B_), (0.64, 0.38, 0.12, P_), (0.4, 0.26, 0.07, G_)):
            d.ellipse([n * (cx - r), n * (cy - r), n * (cx + r), n * (cy + r)], outline=col, width=int(2.5 * S))
    elif kind == "ripple":
        for r, col in ((0.12, "#FFFFFF"), (0.24, B_), (0.36, P_)):
            d.ellipse([n * (0.5 - r), n * (0.5 - r), n * (0.5 + r), n * (0.5 + r)], outline=col, width=int(2.5 * S))
    elif kind == "burst":
        for i in range(10):
            a = 2 * math.pi * i / 10
            col = EZ_COLORS[i % 3]
            x0, y0 = n * (0.5 + math.cos(a) * 0.12), n * (0.5 + math.sin(a) * 0.12)
            x1, y1 = n * (0.5 + math.cos(a) * 0.36), n * (0.5 + math.sin(a) * 0.36)
            d.line([(x0, y0), (x1, y1)], fill=col, width=int(3 * S))
    return im.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- Ứng dụng
class App:
    PW, PH = 316, 300   # kích thước khung xem trước

    def __init__(self, start_in_tray):
        self.cfg = load_cfg()
        global LANG
        LANG = self.cfg["language"]
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

        # Tk gốc (ẩn) và overlay con trỏ trong suốt từng điểm ảnh
        self.ov = tk.Tk()
        self.ov.withdraw()
        self.fxw = LayeredOverlay()      # lớp hiệu ứng, tạo trước để nằm dưới con trỏ
        self.ovl = LayeredOverlay()
        self.fx = FxEngine()
        self.fx_test_until = 0.0
        self.fx_prev_click = False
        self.fx_t = time.perf_counter()
        self.ov_hot = (0, 0)
        self.composed = None
        self.cursor_frames = None
        self.preview_photos = None
        self.cf_idx = 0
        self._cf_job = None
        self.shell_open = False

        self.F = Fonts(self.ov)

        # Cửa sổ chính
        self.win = ctk.CTkToplevel(self.ov, fg_color=BG)
        self.win.title(APP_NAME)
        self.win.geometry("1000x700")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        ico = res_path("ezcursor.ico")
        if ico.exists():
            try:
                self.ov.iconbitmap(default=str(ico))      # icon mặc định cho mọi cửa sổ của app
            except Exception:
                pass
            self.win.after(260, lambda: self.win.iconbitmap(str(ico)))
        self.win.after(320, self.apply_window_icon)
        self.win.after(350, self.fix_window_style)
        try:
            self.sc = self.win._get_window_scaling()
        except Exception:
            self.sc = 1.0

        if self.cfg["image"]:
            self.load_image(self.cfg["image"], silent=True)

        self.build_ui()
        self.splashing = False
        if start_in_tray:
            self.win.withdraw()
            self.win.after(300, self.win.withdraw)
        elif self.cfg["splash"] and logo_frames():
            self.splashing = True
            self.win.withdraw()
            self.win.after(300, lambda: self.win.withdraw() if self.splashing else None)
            self.ov.after(30, self.show_splash)

        menu = pystray.Menu(
            pystray.MenuItem(lambda it: T("Mở EzCursor"), lambda i, it: self.q.put("show"), default=True),
            pystray.MenuItem(lambda it: T("Bật con trỏ"), lambda i, it: self.q.put("toggle"),
                             checked=lambda it: self.enabled),
            pystray.MenuItem(lambda it: T("Kiểm tra cập nhật"), lambda i, it: self.q.put("check_update")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda it: T("Thoát"), lambda i, it: self.q.put("quit")),
        )
        self.icon = pystray.Icon(APP_NAME, make_tray_icon(), APP_NAME, menu)
        self.icon.run_detached()

        self.refresh_apps()
        self.refresh()
        self.tick()
        self.anim()
        self.fx_loop()
        self.ov.after(5000, self.auto_check_update)

    # ------------------------------------------------------------ Tiện ích giao diện
    def caps(self, parent, text, color=MUTED):
        return ctk.CTkLabel(parent, text=T(text), font=self.F.h(11, bold=False), text_color=color)

    def card(self, parent, **kw):
        return ctk.CTkFrame(parent, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=14, **kw)

    def switch(self, parent, var, command):
        return ctk.CTkSwitch(parent, text="", variable=var, command=command, width=50,
                             switch_width=46, switch_height=24, progress_color=ACCENT, fg_color="#1A1E29",
                             button_color="#FFFFFF", button_hover_color="#FFFFFF", border_color="#3A4152")

    def cyan_button(self, parent, text, command, icon=None):
        return ctk.CTkButton(parent, text=T(text), command=command, image=icon, compound="left",
                             height=40, corner_radius=10, border_width=1, border_color=CYAN,
                             fg_color=mix(CARD, CYAN, 0.10), hover_color=mix(CARD, CYAN, 0.22),
                             text_color=CYAN_TEXT, font=self.F.b(13, strong=True))

    def header(self, parent, title, sub):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text=T(title), font=self.F.h(24), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(f, text=T(sub), font=self.F.b(13), text_color=TEXT2).pack(anchor="w")
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
            "library": self.build_library_tab(self.content),
            "fx": self.build_fx_tab(self.content),
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
        self.logo_ctk = [ctk.CTkImage(fr.resize((64, 64), Image.LANCZOS), size=(30, 30)) for fr in logo_frames()]
        self.logo_lbl = ctk.CTkLabel(logo, text="", image=self.logo_ctk[0] if self.logo_ctk
                                     else ctk.CTkImage(logo_image(64), size=(30, 30)))
        self.logo_lbl.pack(side="left")
        ctk.CTkLabel(logo, text=" EZ", font=self.F.h(18), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(logo, text="CURSOR", font=self.F.h(18), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(logo, text=f"v{APP_VERSION}", font=self.F.m(10), text_color=MUTED,
                     fg_color="#151922", corner_radius=6, width=10).pack(side="left", padx=(8, 0))

        self.caps(sb, "MENU").pack(anchor="w", padx=24, pady=(0, 6))
        self.nav_buttons = {}
        for key, label in (("cursor", "Con trỏ"), ("library", "Bộ sưu tập"), ("fx", "Hiệu ứng"),
                           ("apps", "Ứng dụng"), ("opts", "Tùy chọn")):
            icons = (ctk.CTkImage(nav_icon(key, "#FFFFFF", 40), size=(20, 20)),
                     ctk.CTkImage(nav_icon(key, TEXT2, 40), size=(20, 20)))
            b = ctk.CTkButton(sb, text="  " + T(label), anchor="w", height=46, corner_radius=10,
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
        ctk.CTkLabel(row, text=T("Bật EzCursor"), font=self.F.b(14, strong=True), text_color=TEXT).pack(side="left")
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
            b = ctk.CTkButton(grid, text=T(label), height=38, width=10, corner_radius=9, border_width=1,
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
        self.img_label = ctk.CTkLabel(row, text=T("(chưa có ảnh)"), font=self.F.m(12), text_color=TEXT2)
        self.img_label.pack(side="left", padx=10)
        if self.cfg["image"] and self.src_img is not None:
            self.img_label.configure(text=Path(self.cfg["image"]).name)

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(row, text=T("Điểm click"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.hot_map = {T(h): h for h in HOTSPOTS}
        self.hot_seg = ctk.CTkSegmentedButton(row, values=list(self.hot_map),
                                              command=lambda v: self.set_hotspot(self.hot_map[v]), height=30,
                                              font=self.F.b(12), fg_color=FIELD, unselected_color=FIELD,
                                              unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                                              selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        self.hot_seg.set(T(self.cfg["hotspot"]))
        self.hot_seg.pack(side="right")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(row, text=T("Tô màu cho ảnh tải lên"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.tint_var = tk.BooleanVar(value=self.cfg["tint_image"])
        self.switch(row, self.tint_var, self.set_tint).pack(side="right")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text=T("Quầng sáng quanh con trỏ"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.glow_var = tk.BooleanVar(value=self.cfg["glow"])
        self.switch(row, self.glow_var, self.set_glow).pack(side="right")
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

    # ------------------------------------------------------------ Tab Bộ sưu tập (Bibata)
    def build_library_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.header(page, "BỘ SƯU TẬP", "Con trỏ của EzCursor và bộ Bibata. Bấm vào con trỏ muốn dùng.").pack(
            anchor="w", pady=(0, 14))
        self.bib_tiles = {}
        if not BIBATA_DIR.exists():
            ctk.CTkLabel(page, text=T("Không tìm thấy thư mục bibata đi kèm phần mềm."), font=self.F.b(13),
                         text_color=AMBER).pack(anchor="w")
            return page

        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x")
        self.caps(top, "CHỦ ĐỀ").pack(anchor="w")
        chips = ctk.CTkFrame(top, fg_color="transparent")
        chips.pack(fill="x", pady=(6, 12))
        self.theme_buttons = {}
        themes = [(k, v[0], v[1]) for k, v in BIBATA_THEMES.items()] + [("custom", T("Tùy chỉnh"), None)]
        for key, label, col in themes:
            b = ctk.CTkButton(chips, text=label, height=40, width=118, corner_radius=10, border_width=1,
                              font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_bib("bibata_theme", k))
            b.pack(side="left", padx=(0, 8))
            self.theme_buttons[key] = b

        self.caps(page, "MÀU TÙY CHỈNH").pack(anchor="w")
        sw = ctk.CTkFrame(page, fg_color="transparent")
        sw.pack(fill="x", pady=(6, 12))
        self.bib_swatches = {}
        for c, name in SWATCHES:
            b = ctk.CTkButton(sw, text="", width=32, height=32, corner_radius=16, fg_color=c,
                              hover_color=mix(c, "#FFFFFF", 0.2), border_width=0,
                              command=lambda c=c: self.set_bib_color(c))
            b.pack(side="left", padx=(0, 7))
            self.bib_swatches[c] = b
        for c in ("#FFFFFF", "#000000"):
            b = ctk.CTkButton(sw, text="", width=32, height=32, corner_radius=16, fg_color=c,
                              hover_color=mix(c, "#808080", 0.25), border_width=1, border_color="#4A5266",
                              command=lambda c=c: self.set_bib_color(c))
            b.pack(side="left", padx=(0, 7))
            self.bib_swatches[c] = b
        self.bib_custom_btn = ctk.CTkButton(sw, text="", width=32, height=32, corner_radius=16,
                                            image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)),
                                            fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                            border_color="#4A5266", command=self.pick_bib_color)
        self.bib_custom_btn.pack(side="left")

        opts = ctk.CTkFrame(page, fg_color="transparent")
        opts.pack(fill="x", pady=(0, 12))
        seg_kw = dict(height=34, font=self.F.b(12, strong=True), fg_color=FIELD, unselected_color=FIELD,
                      unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                      selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        self.style_map = {T("Modern · bo tròn"): "modern", T("Original · góc nhọn"): "original"}
        self.hand_map = {T("Thuận tay phải"): "right", T("Thuận tay trái"): "left"}
        self.style_seg = ctk.CTkSegmentedButton(opts, values=list(self.style_map),
                                                command=lambda v: self.set_bib("bibata_style", self.style_map[v]), **seg_kw)
        self.style_seg.pack(side="left")
        self.hand_seg = ctk.CTkSegmentedButton(opts, values=list(self.hand_map),
                                               command=lambda v: self.set_bib("bibata_hand", self.hand_map[v]), **seg_kw)
        self.hand_seg.pack(side="right")
        inv_style = {v: k for k, v in self.style_map.items()}
        inv_hand = {v: k for k, v in self.hand_map.items()}
        self.style_seg.set(inv_style.get(self.cfg["bibata_style"], T("Modern · bo tròn")))
        self.hand_seg.set(inv_hand.get(self.cfg["bibata_hand"], T("Thuận tay phải")))

        grid = self.card(page)
        grid.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(grid, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=10)
        cols = 5
        for i in range(cols):
            inner.grid_columnconfigure(i, weight=1, uniform="t")
        self.own_tiles = {}
        for shape, label, _f, _h, _g in OWN_CURSORS:
            img = own_image(shape)
            if img is None:
                continue
            b = ctk.CTkButton(inner, text=T(label), compound="top", height=94, width=10, corner_radius=12,
                              border_width=1, font=self.F.b(12, strong=True),
                              image=ctk.CTkImage(img.resize((112, 112), Image.LANCZOS), size=(56, 56)),
                              command=lambda sh=shape: self.pick_own(sh))
            n = len(self.own_tiles)
            b.grid(row=0, column=n, sticky="ew", padx=4, pady=4)
            self.own_tiles[shape] = b
        offset = len(self.own_tiles)
        for i, (name, label) in enumerate(BIBATA_CURSORS):
            i += offset
            b = ctk.CTkButton(inner, text=T(label), compound="top", height=94, width=10, corner_radius=12, border_width=1,
                              font=self.F.b(12), command=lambda n=name: self.pick_bibata(n))
            b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            self.bib_tiles[name] = b

        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(foot, text=T("Chọn một màu để chuyển sang chủ đề Tùy chỉnh."), font=self.F.b(12),
                     text_color=TEXT2).pack(side="left")
        link = ctk.CTkLabel(foot, text="Bibata © Abdulkaiz Khatri · GPL-3.0", font=self.F.b(12),
                            text_color=CYAN_TEXT, cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ful1e5/Bibata_Cursor"))
        self._lib_sig = None
        return page

    def set_bib_color(self, color):
        self.cfg["color"] = color
        self.cfg["bibata_theme"] = "custom"
        if self.cfg["shape"] != "Bibata":
            self.cfg["shape"] = "Bibata"
        self.refresh()

    def pick_bib_color(self):
        res = colorchooser.askcolor(color=self.cfg["color"], parent=self.win, title=T("Chọn màu"))
        if res and res[1]:
            self.set_bib_color(res[1])

    def set_bib(self, key, value):
        self.cfg[key] = value
        self.refresh()

    def pick_own(self, shape):
        self.cfg["shape"] = shape
        self.refresh()

    def pick_bibata(self, name):
        self.cfg["bibata_cursor"] = name
        self.cfg["shape"] = "Bibata"
        self.refresh()

    def update_library(self):
        if not getattr(self, "bib_tiles", None):
            return
        c = self.cfg
        for key, b in self.theme_buttons.items():
            col = BIBATA_THEMES[key][1] if key in BIBATA_THEMES else c["color"]
            dot = ctk.CTkImage(_ss(lambda d, s, col=col: d.ellipse(
                [1 * s, 1 * s, 15 * s, 15 * s], fill=col, outline="#FFFFFF", width=int(1.5 * s)), 16), size=(14, 14))
            on = key == c["bibata_theme"]
            b.configure(image=dot, fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)
        custom_on = c["bibata_theme"] == "custom"
        known = set()
        for col, b in self.bib_swatches.items():
            known.add(col.lower())
            on = custom_on and col.lower() == c["color"].lower()
            plain = col in ("#FFFFFF", "#000000")
            b.configure(border_width=3 if on else (1 if plain else 0),
                        border_color=ACCENT if (on and col == "#FFFFFF") else ("#FFFFFF" if on else "#4A5266"))
        if custom_on and c["color"].lower() not in known:
            self.bib_custom_btn.configure(fg_color=c["color"], hover_color=c["color"], border_width=3,
                                          border_color="#FFFFFF", image=None)
        else:
            self.bib_custom_btn.configure(fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                          border_color="#4A5266",
                                          image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)))
        variant = self.bibata_variant()
        colors = bibata_colors(c["bibata_theme"], c["color"])
        sig = (variant, colors)
        if sig != self._lib_sig:          # chỉ vẽ lại hình khi đổi chủ đề / kiểu dáng
            self._lib_sig = sig
            for name, b in self.bib_tiles.items():
                im = bibata_image(BIBATA_DIR, variant, name, colors).resize((112, 112), Image.LANCZOS)
                b.configure(image=ctk.CTkImage(im, size=(56, 56)))
        tile_bg = mix(FIELD, "#FFFFFF", 0.05) if c["bibata_theme"] == "classic" else FIELD
        for shape, tile in self.own_tiles.items():
            on = c["shape"] == shape
            tile.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                           hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                           border_color=ACCENT if on else mix(BORDER, ACCENT, 0.35),
                           text_color="#FFFFFF" if on else TEXT)
        for name, b in self.bib_tiles.items():
            on = c["shape"] == "Bibata" and name == c["bibata_cursor"]
            b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else tile_bg,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)


    # ------------------------------------------------------------ Tab Hiệu ứng
    def build_fx_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.header(page, "HIỆU ỨNG", "Thêm vệt sáng theo con trỏ và hiệu ứng khi click trong game.").pack(
            anchor="w", pady=(0, 14))
        self.fx_tiles = {}

        def tile_group(title, options, key):
            card = self.card(page)
            card.pack(fill="x", pady=(0, 12))
            self.caps(card, title).pack(anchor="w", padx=14, pady=(12, 6))
            grid = ctk.CTkFrame(card, fg_color="transparent")
            grid.pack(fill="x", padx=10, pady=(0, 12))
            for i in range(6):
                grid.grid_columnconfigure(i, weight=1, uniform="fx")
            for i, (val, label) in enumerate(options):
                b = ctk.CTkButton(grid, text=T(label), compound="top", height=84, width=10, corner_radius=12, border_width=1,
                                  image=ctk.CTkImage(fx_icon(val, 96), size=(42, 42)), font=self.F.b(12),
                                  command=lambda v=val, k=key: self.set_fx(k, v))
                b.grid(row=0, column=i, sticky="ew", padx=4)
                self.fx_tiles[(key, val)] = b

        tile_group("VỆT THEO CON TRỎ", FX_TRAILS, "fx_trail")

        # Hai nhóm nhỏ chung một hàng: khi click và quanh con trỏ
        card = self.card(page)
        card.pack(fill="x", pady=(0, 12))
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=(4, 12))
        for i in range(6):
            grid.grid_columnconfigure(i, weight=1, uniform="fx")
        self.caps(grid, "KHI CLICK CHUỘT TRÁI").grid(row=0, column=0, columnspan=3, sticky="w", padx=4, pady=(8, 6))
        self.caps(grid, "QUANH CON TRỎ").grid(row=0, column=4, columnspan=2, sticky="w", padx=4, pady=(8, 6))
        groups = [(0, FX_CLICKS, "fx_click"), (4, [(False, "Tắt"), (True, "Lấp lánh")], "cursor_sparkle")]
        for start, options, key in groups:
            for i, (val, label) in enumerate(options):
                icon = val if isinstance(val, str) else ("aura" if val else "off")
                b = ctk.CTkButton(grid, text=T(label), compound="top", height=84, width=10, corner_radius=12,
                                  border_width=1, image=ctk.CTkImage(fx_icon(icon, 96), size=(40, 40)),
                                  font=self.F.b(12), command=lambda v=val, k=key: self.set_fx(k, v))
                b.grid(row=1, column=start + i, sticky="ew", padx=4)
                self.fx_tiles[(key, val)] = b

        opt = self.card(page)
        opt.pack(fill="x")
        seg_kw = dict(height=32, font=self.F.b(12, strong=True), fg_color=FIELD, unselected_color=FIELD,
                      unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                      selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        self.fx_color_map = {T("Theo màu con trỏ"): "cursor", T("Ba màu EzCursor"): "ez"}
        self.fx_dens_map = {T("Ít"): "low", T("Vừa"): "mid", T("Nhiều"): "high"}
        row = ctk.CTkFrame(opt, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(row, text=T("Màu hiệu ứng"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.fx_color_seg = ctk.CTkSegmentedButton(row, values=list(self.fx_color_map),
                                                   command=lambda v: self.set_fx("fx_color", self.fx_color_map[v]), **seg_kw)
        self.fx_color_seg.pack(side="right")
        row = ctk.CTkFrame(opt, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 12))
        ctk.CTkLabel(row, text=T("Mật độ"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.fx_dens_seg = ctk.CTkSegmentedButton(row, values=list(self.fx_dens_map),
                                                  command=lambda v: self.set_fx("fx_density", self.fx_dens_map[v]), **seg_kw)
        self.fx_dens_seg.pack(side="right")

        inv = {v: k for k, v in self.fx_color_map.items()}
        self.fx_color_seg.set(inv.get(self.cfg["fx_color"], T("Theo màu con trỏ")))
        inv = {v: k for k, v in self.fx_dens_map.items()}
        self.fx_dens_seg.set(inv.get(self.cfg["fx_density"], T("Vừa")))

        test = ctk.CTkFrame(page, fg_color="transparent")
        test.pack(fill="x", pady=(14, 0))
        self.fx_test_btn = ctk.CTkButton(test, text=T("THỬ NGAY TRÊN MÀN HÌNH"), command=self.fx_test, height=44,
                                         width=240, corner_radius=10, fg_color=ACCENT,
                                         hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        self.fx_test_btn.pack(side="left")
        ctk.CTkLabel(test, text=T("   Di chuột và click trong 8 giây để xem hiệu ứng."), font=self.F.b(12),
                     text_color=TEXT2).pack(side="left")
        return page

    def set_fx(self, key, value):
        self.cfg[key] = value
        if key == "cursor_sparkle":
            self.refresh()          # cần tạo lại khung hình con trỏ
        else:
            self.update_fx_ui()
            self.save()

    def update_fx_ui(self):
        if not getattr(self, "fx_tiles", None):
            return
        for (key, val), b in self.fx_tiles.items():
            on = self.cfg[key] == val
            b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)

    def fx_test(self):
        if self.cfg["fx_trail"] == "off" and self.cfg["fx_click"] == "off":
            messagebox.showinfo(APP_NAME, T("Hãy chọn ít nhất một hiệu ứng trước khi thử."), parent=self.win)
            return
        self.fx_test_until = time.perf_counter() + 8
        self.fx_test_btn.configure(text=T("ĐANG THỬ..."), state="disabled")
        self.win.after(8000, lambda: self.fx_test_btn.configure(text=T("THỬ NGAY TRÊN MÀN HÌNH"), state="normal"))

    def fx_palette(self):
        if self.cfg["fx_color"] == "ez":
            return EZ_COLORS
        g = self.glow_color()
        return [g, mix(g, "#FFFFFF", 0.45)]

    def fx_loop(self):
        """Vòng lặp hiệu ứng ~60 khung/giây, chỉ vẽ khi có hạt đang hiện."""
        try:
            now = time.perf_counter()
            dt = min(0.05, now - self.fx_t)
            self.fx_t = now
            c = self.cfg
            self.fx_tick = getattr(self, "fx_tick", 0) + 1
            if self.cursor_frames and self.active and self.fx_tick % 6 == 0:
                self.cf_idx = (self.cf_idx + 1) % len(self.cursor_frames)
                self.ovl.set_image(self.cursor_frames[self.cf_idx])
            on = c["fx_trail"] != "off" or c["fx_click"] != "off"
            want = on and (self.active or now < self.fx_test_until)
            if want or self.fx.busy():
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                down = bool(key_down(VK_LBUTTON))
                clicked = want and down and not self.fx_prev_click
                self.fx_prev_click = down
                pal = self.fx_palette()
                cfg_now = c if want else dict(c, fx_trail="off")
                ghost = self.composed[0] if self.composed else None
                self.fx.update(now, dt, (pt.x, pt.y), clicked, cfg_now, pal, ghost)
                img, pos = self.fx.render(now, (pt.x, pt.y), cfg_now, pal, self.ov_hot)
                if img is None:
                    self.fxw.show(False)
                else:
                    self.fxw.set_image(img, pos)
                    if not self.fxw.visible:
                        self.fxw.show(True)
                        user32.SetWindowPos(self.fxw.hwnd, self.ovl.hwnd, 0, 0, 0, 0, 0x2 | SWP_NOSIZE | SWP_NOACTIVATE)
            else:
                self.fxw.show(False)
                self.fx.last = None
        except tk.TclError:
            return
        except Exception:
            pass
        self.ov.after(16, self.fx_loop)

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
        ctk.CTkLabel(bottom, text=T("  Áp dụng cho mọi ứng dụng (kể cả Desktop)"), font=self.F.b(13),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(bottom, text=T("ÁP DỤNG"), command=self.apply_apps, height=44, width=150, corner_radius=10,
                      fg_color=ACCENT, hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF",
                      font=self.F.h(15)).pack(side="right")
        self.applied_label = ctk.CTkLabel(page, text="", font=self.F.b(12), text_color=TEXT2, anchor="w",
                                          justify="left", wraplength=680)
        self.applied_label.pack(fill="x", pady=(10, 0))
        self.update_applied_label()
        return page

    def build_options_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.header(page, "TÙY CHỌN", "Cài đặt chung, cập nhật và phím tắt.").pack(anchor="w", pady=(0, 12))

        box = self.card(page)
        box.pack(fill="x")

        r = ctk.CTkFrame(box, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=(7, 0))
        t = ctk.CTkFrame(r, fg_color="transparent")
        t.pack(side="left")
        ctk.CTkLabel(t, text=T("Ngôn ngữ"), font=self.F.b(14, strong=True), text_color=TEXT, height=20).pack(anchor="w")
        ctk.CTkLabel(t, text=T("Ngôn ngữ hiển thị của EzCursor."), font=self.F.b(12), text_color=TEXT2,
                     height=18).pack(anchor="w")
        self.lang_map = {name: code for code, name in LANGUAGES}
        self.lang_seg = ctk.CTkSegmentedButton(
            r, values=list(self.lang_map), command=lambda v: self.set_language(self.lang_map[v]), height=32,
            font=self.F.b(12, strong=True), fg_color=FIELD, unselected_color=FIELD,
            unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
            selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        self.lang_seg.set(dict(LANGUAGES)[self.cfg["language"]])
        self.lang_seg.pack(side="right")
        ctk.CTkFrame(box, fg_color=LINE, height=1, corner_radius=0).pack(fill="x", padx=18, pady=(7, 0))

        self.hide_var = tk.BooleanVar(value=self.cfg["hide_real"])
        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        self.auto_upd_var = tk.BooleanVar(value=self.cfg["auto_check_update"])
        self.splash_var = tk.BooleanVar(value=self.cfg["splash"])
        rows = [("Ẩn con trỏ thật của game", "Chỉ hiện con trỏ của EzCursor khi đang ở trong game.",
                 self.hide_var, self.set_hide),
                ("Khởi động cùng Windows", "Chạy ngầm dưới khay hệ thống khi bật máy.",
                 self.startup_var, self.set_startup_opt),
                ("Tự động kiểm tra cập nhật", "Thông báo khi có phiên bản mới trên GitHub.",
                 self.auto_upd_var, self.set_auto_update),
                ("Màn hình chào khi mở", "Hiện logo động khoảng 2 giây mỗi lần mở EzCursor.",
                 self.splash_var, self.set_splash)]
        for title, sub, var, cmd in rows:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=18, pady=(7, 0))
            t = ctk.CTkFrame(r, fg_color="transparent")
            t.pack(side="left")
            ctk.CTkLabel(t, text=T(title), font=self.F.b(14, strong=True), text_color=TEXT, height=20).pack(anchor="w")
            ctk.CTkLabel(t, text=T(sub), font=self.F.b(12), text_color=TEXT2, height=18).pack(anchor="w")
            self.switch(r, var, cmd).pack(side="right")
            ctk.CTkFrame(box, fg_color=LINE, height=1, corner_radius=0).pack(fill="x", padx=18, pady=(7, 0))

        r = ctk.CTkFrame(box, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=12)
        t = ctk.CTkFrame(r, fg_color="transparent")
        t.pack(side="left")
        v = ctk.CTkFrame(t, fg_color="transparent")
        v.pack(anchor="w")
        ctk.CTkLabel(v, text=T("Phiên bản "), font=self.F.b(14, strong=True), text_color=TEXT, height=20).pack(side="left")
        ctk.CTkLabel(v, text=APP_VERSION, font=self.F.m(13), text_color=ACCENT, height=20).pack(side="left")
        self.upd_label = ctk.CTkLabel(t, text="", font=self.F.b(12), text_color=TEXT2, height=18)
        self.upd_label.pack(anchor="w")
        self.cyan_button(r, "Kiểm tra cập nhật", lambda: self.check_update(manual=True)).pack(side="right")

        r = ctk.CTkFrame(box, fg_color="transparent")
        r.pack(fill="x", padx=18, pady=(0, 12))
        t = ctk.CTkFrame(r, fg_color="transparent")
        t.pack(side="left")
        ctk.CTkLabel(t, text=T("Khôi phục cài đặt gốc"), font=self.F.b(14, strong=True), text_color=TEXT,
                     height=20).pack(anchor="w")
        ctk.CTkLabel(t, text=T("Xóa mọi lựa chọn đã lưu và khởi động lại EzCursor như mới cài."),
                     font=self.F.b(12), text_color=TEXT2, height=18).pack(anchor="w")
        ctk.CTkButton(r, text=T("Khôi phục"), command=self.reset_settings, height=40, width=120, corner_radius=10,
                      border_width=1, border_color="#FF5A5A", fg_color=mix(CARD, "#FF5A5A", 0.10),
                      hover_color=mix(CARD, "#FF5A5A", 0.22), text_color="#FF8A8A",
                      font=self.F.b(13, strong=True)).pack(side="right")

        hk = self.card(page)
        hk.pack(fill="x", pady=(12, 0))
        self.caps(hk, "PHÍM TẮT").pack(anchor="w", padx=16, pady=(12, 6))
        grid = ctk.CTkFrame(hk, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 12))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="h")
        keys = [("Bật / tắt", "H"), ("Đổi hình dạng", "R"), ("Đổi màu", "1–5"), ("Thoát", "Q")]
        for i, (desc, k) in enumerate(keys):
            cell = ctk.CTkFrame(grid, fg_color=FIELD, border_color=LINE, border_width=1, corner_radius=10)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
            ctk.CTkLabel(cell, text=T(desc), font=self.F.b(13), text_color="#C9CFDB").pack(side="left", padx=12, pady=10)
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
            return T("●  ĐANG TẮT"), MUTED, T("Con trỏ gốc đang được dùng.")
        if self.active:
            sub = T("Áp dụng cho mọi ứng dụng.") if self.cfg["all_apps"] else T("Trong game: ") + self.fg_exe
            return T("●  ĐANG HOẠT ĐỘNG"), GREEN, sub
        if self.shell_open:
            return T("●  TẠM DỪNG"), AMBER, T("Đang ở trên giao diện của Windows.")
        if not self.cfg["apps"]:
            return T("●  CHƯA CHỌN GAME"), AMBER, T("Vào tab Ứng dụng để chọn game.")
        return T("●  ĐANG CHỜ GAME"), AMBER, T("Chờ: ") + ", ".join(self.cfg["apps"])

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

    def glow_color(self):
        return self.composed[2] if self.composed else self.preview_color()

    def compose_cursor(self):
        """Ảnh con trỏ hoàn chỉnh dùng cho cả overlay lẫn xem trước: (ảnh, điểm click, màu quầng)."""
        c = self.cfg
        s = c["size"]
        if own_image(c["shape"]) is not None:
            _, _, _, (hx, hy), glow_col = OWN_BY_ID[c["shape"]]
            im = own_image(c["shape"]).resize((s, s), Image.LANCZOS)
            hot = (round(hx * s / 256), round(hy * s / 256))
        elif c["shape"] == "Bibata" and BIBATA_DIR.exists():
            variant = self.bibata_variant()
            cols = bibata_colors(c["bibata_theme"], c["color"])
            im = bibata_image(BIBATA_DIR, variant, c["bibata_cursor"], cols).resize((s, s), Image.LANCZOS)
            hx, hy = BIBATA_META["hotspots"].get(f"{variant}/{c['bibata_cursor']}", [128, 128])
            hot = (round(hx * s / 256), round(hy * s / 256))
            glow_col = cols[0] if luminance(cols[0]) > 60 else cols[1]
        else:
            shape = c["shape"] if c["shape"] not in ("Bibata",) + tuple(OWN_BY_ID) else "Vòng tròn"
            src = self.src_img
            if src is not None and c["tint_image"]:
                src = tint_image(src, c["color"])
            glow_col = self.preview_color()
            im, hot = render_shape(shape, glow_col, s, src, c["hotspot"])
        if c["glow"]:
            im, hot = add_glow(im, hot, glow_col)
        return im, hot, glow_col

    def bibata_variant(self):
        return self.cfg["bibata_style"] + ("-right" if self.cfg["bibata_hand"] == "left" else "")

    def rebuild_overlay(self):
        self.composed = self.compose_cursor()
        im, self.ov_hot, _ = self.composed
        self.cursor_frames = None
        self.preview_photos = None
        self.ovl.set_image(im)
        if getattr(self, "_cf_job", None):
            self.ov.after_cancel(self._cf_job)
            self._cf_job = None
        if self.cfg["cursor_sparkle"]:
            self._cf_job = self.ov.after(160, self.build_cursor_frames)

    def build_cursor_frames(self):
        """Tạo 24 khung hình con trỏ có ngôi sao nhấp nháy quanh (vòng lặp ~2,4 giây)."""
        self._cf_job = None
        if not self.composed:
            return
        im, hot, gcol = self.composed
        s = self.cfg["size"]
        bb = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, im.width, im.height)
        pad = max(8, s // 4)
        W, H = im.width + 2 * pad, im.height + 2 * pad
        x0, y0, x1, y1 = (v + pad for v in bb)
        bw, bh = x1 - x0, y1 - y0
        spots = [  # (x, y, bán kính, màu, thời điểm sáng nhất)
            (x1 - 0.02 * bw, y0 + 0.10 * bh, s * 0.12, "#FFFFFF", 0.15),
            (x1 + 0.06 * bw, y0 + 0.42 * bh, s * 0.075, "#2EE59D", 0.48),
            (x0 + 0.02 * bw, y1 - 0.02 * bh, s * 0.065, gcol, 0.78),
        ]
        frames = []
        N = 24
        for i in range(N):
            t = i / N
            fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fr.alpha_composite(im, (pad, pad))
            for x, y, R, col, ctr in spots:
                d = min(abs(t - ctr), 1 - abs(t - ctr))
                p = max(0.0, math.cos(min(1.0, d / 0.2) * math.pi / 2)) ** 1.5
                if p < 0.04:
                    continue
                size = max(8, int(R * (0.45 + 0.7 * p) / 0.36))
                st = self.fx.sprite("star", col, size)
                st = self.fx.faded(("star", col, size), st, min(1.0, p * 1.3))
                if st is None:
                    continue
                px, py = int(x - st.width / 2), int(y - st.height / 2)
                if 0 <= px and 0 <= py and px + st.width <= W and py + st.height <= H:
                    fr.alpha_composite(st, (px, py))
            frames.append(fr)
        self.cursor_frames = frames
        self.cf_idx = 0
        self.ov_hot = (hot[0] + pad, hot[1] + pad)
        self.ovl.set_image(frames[0])
        if self.active:
            self.move_overlay()
        self.preview_photos = [ImageTk.PhotoImage(fr, master=self.ov) for fr in frames]

    def update_preview(self):
        c = self.cfg
        if self.composed is None:
            self.rebuild_overlay()
        im = self.composed[0]
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
        self.rebuild_overlay()
        self.update_controls()
        self.update_library()
        self.update_fx_ui()
        self.update_preview()
        self.update_status()
        self.save()

    def compute_active(self):
        if not self.enabled:
            return False
        self.shell_open = shell_ui_open()
        if self.shell_open:          # menu Start, Search, Alt+Tab... -> dùng con trỏ thật
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
        if on:
            self.move_overlay()
        self.ovl.show(on)
        self.update_status()

    # ------------------------------------------------------------ Danh sách ứng dụng
    def refresh_apps(self):
        _name_cache.clear()
        running = list_running_apps()
        running_names = {n.lower() for n, _ in running}
        items = [(n, t, True) for n, t in running]
        items += [(n, T("(đang không chạy)"), False) for n in self.cfg["apps"] if n.lower() not in running_names]
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
        badge = ctk.CTkLabel(row, text=T(" ĐANG CHẠY ") if running else T(" KHÔNG CHẠY "), font=self.F.m(10),
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
        txt = (T("Đang áp dụng cho: ") + ", ".join(self.cfg["apps"])) if self.cfg["apps"] else T("Chưa chọn ứng dụng nào.")
        if just_applied:
            txt = T("✓ Đã áp dụng.  ") + txt
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
        options = [x for x in SHAPES if x != "Ảnh tải lên" or self.src_img is not None]
        cur = self.cfg["shape"]
        i = options.index(cur) if cur in options else -1
        self.set_shape(options[(i + 1) % len(options)])

    def set_color(self, color):
        if color.lower() == TRANSPARENT:
            color = "#020202"
        self.cfg["color"] = color
        if self.cfg["shape"] == "Bibata":
            self.cfg["bibata_theme"] = "custom"
        self.refresh()

    def pick_color(self):
        res = colorchooser.askcolor(color=self.cfg["color"], parent=self.win, title=T("Chọn màu"))
        if res and res[1]:
            self.set_color(res[1])

    def set_size(self, s):
        if s == self.cfg["size"]:
            return
        self.cfg["size"] = s
        self.refresh()

    def set_tint(self):
        self.cfg["tint_image"] = bool(self.tint_var.get())
        self.refresh()

    def set_glow(self):
        self.cfg["glow"] = bool(self.glow_var.get())
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
            messagebox.showerror(T("Lỗi"), T("Không thay đổi được cài đặt khởi động:") + f"\n{e}", parent=self.win)
            self.startup_var.set(is_startup_enabled())

    def upload_image(self):
        path = filedialog.askopenfilename(
            parent=self.win, title=T("Chọn ảnh con trỏ"),
            filetypes=[(T("Ảnh"), "*.png *.gif *.webp *.ico *.bmp *.jpg *.jpeg"), (T("Tất cả"), "*.*")])
        if not path:
            return
        dest = APP_DIR / ("custom" + Path(path).suffix.lower())
        try:
            shutil.copyfile(path, dest)
        except Exception as e:
            messagebox.showerror(T("Lỗi"), T("Không sao chép được ảnh:") + f"\n{e}", parent=self.win)
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
                messagebox.showerror(T("Lỗi"), T("Không mở được ảnh:") + f"\n{e}", parent=self.win)
            return False
        return True

    def move_overlay(self):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        self.ovl.move(pt.x - self.ov_hot[0], pt.y - self.ov_hot[1])

    def hide_to_tray(self):
        self.win.withdraw()
        if not self.cfg["tray_hint_shown"]:
            self.cfg["tray_hint_shown"] = True
            self.save()
            try:
                self.icon.notify(T("EzCursor vẫn đang chạy dưới khay hệ thống. "
                                   "Chuột phải vào icon để mở lại hoặc thoát."), APP_NAME)
            except Exception:
                pass

    def apply_window_icon(self):
        """Icon độ phân giải cao cho thanh tiêu đề và taskbar."""
        for name in ("logo.png", "ezcursor.ico"):
            p = res_path(name)
            if p.exists():
                try:
                    im = Image.open(p).convert("RGBA")
                    self._win_icons = [ImageTk.PhotoImage(im.resize((n, n), Image.LANCZOS), master=self.ov)
                                       for n in (256, 64, 32, 16)]
                    self.win.iconphoto(False, *self._win_icons)
                    return
                except Exception:
                    pass

    def fix_window_style(self):
        """Cửa sổ chính là cửa sổ độc lập, không 'luôn trên cùng', để chuyển app khác thì lùi xuống."""
        try:
            hwnd = user32.GetParent(self.win.winfo_id())
            if not hwnd:
                return
            user32.SetWindowLongPtrW(hwnd, -8, 0)                       # GWLP_HWNDPARENT: bỏ cửa sổ sở hữu
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex & ~0x8)          # bỏ WS_EX_TOPMOST
            dwm = ctypes.windll.dwmapi
            for attr, val in ((20, 1),                      # chế độ tối cho thanh tiêu đề
                              (35, 0x00120D0B),             # màu nền thanh tiêu đề = BG
                              (36, 0x00F0EAE8),             # màu chữ tiêu đề
                              (34, 0x00382B26)):            # màu viền cửa sổ
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
            user32.SetWindowPos(hwnd, wintypes.HWND(-2), 0, 0, 0, 0,     # HWND_NOTOPMOST
                                0x2 | 0x1 | 0x10 | 0x20)                 # NOMOVE|NOSIZE|NOACTIVATE|FRAMECHANGED
        except Exception:
            pass

    def show_window(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.win.after(50, self.fix_window_style)
        if self.pending_update:
            info, self.pending_update = self.pending_update, None
            self.show_update_dialog(info, manual=False)

    # ------------------------------------------------------------ Cập nhật
    def reset_settings(self):
        if not messagebox.askyesno(APP_NAME, T("Khôi phục toàn bộ cài đặt về mặc định?\n\n"
                                     "Danh sách game, con trỏ, hiệu ứng và ảnh đã tải lên sẽ bị xóa. "
                                     "EzCursor sẽ tự khởi động lại."), parent=self.win):
            return
        for f in APP_DIR.glob("custom.*"):
            try:
                f.unlink()
            except OSError:
                pass
        self.cfg = dict(DEFAULT_CFG)
        self.cfg["apps"] = []
        self.enabled = True
        self.save()
        if getattr(sys, "frozen", False):
            args = f'"{sys.executable}"'
        else:
            pyw = Path(sys.executable).with_name("pythonw.exe")
            args = f'"{pyw if pyw.exists() else sys.executable}" "{Path(__file__).resolve()}"'
        # đợi bản hiện tại thoát hẳn rồi mới mở lại
        subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & start "" {args}',
                         shell=True, creationflags=0x08000000)
        self.quit()

    def set_language(self, code):
        """Đổi ngôn ngữ giao diện và dựng lại toàn bộ giao diện ngay, không cần khởi động lại."""
        global LANG
        if code == self.cfg["language"]:
            return
        self.cfg["language"] = code
        LANG = code
        self.save()
        self.win.after(20, self.rebuild_ui)

    def rebuild_ui(self):
        tab = self.tab
        for w in self.win.winfo_children():
            w.destroy()
        self.build_ui()
        self.refresh_apps()
        self.refresh()
        self.show_tab(tab)
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def set_splash(self):
        self.cfg["splash"] = bool(self.splash_var.get())
        self.save()

    def show_splash(self):
        """Màn hình chào: logo động ở giữa màn hình, hiện dần rồi mờ dần (~2 giây)."""
        import tkinter.font as tkfont
        sc = self.sc
        W, H = int(340 * sc), int(340 * sc)
        sp = tk.Toplevel(self.ov)
        sp.overrideredirect(True)
        sp.attributes("-topmost", True)
        sp.configure(bg=BG)
        sp.geometry(f"{W}x{H}+{(sp.winfo_screenwidth() - W) // 2}+{(sp.winfo_screenheight() - H) // 2}")
        try:
            sp.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        try:   # bo góc trên Windows 11
            hwnd = user32.GetParent(sp.winfo_id())
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        cv = tk.Canvas(sp, width=W, height=H, bg=BG, highlightthickness=1, highlightbackground=BORDER, bd=0)
        cv.pack()
        size = int(200 * sc)
        photos = [ImageTk.PhotoImage(fr.resize((size, size), Image.LANCZOS), master=self.ov) for fr in logo_frames()]
        img_id = cv.create_image(W // 2, int(H * 0.42), image=photos[0])
        font = tkfont.Font(root=self.ov, family=self.F.head, size=20, weight="bold")
        w1, w2 = font.measure("EZ"), font.measure("CURSOR")
        x0, ty = W / 2 - (w1 + w2) / 2, int(H * 0.81)
        cv.create_text(x0, ty, anchor="w", text="EZ", fill=TEXT, font=font)
        cv.create_text(x0 + w1, ty, anchor="w", text="CURSOR", fill=ACCENT, font=font)
        cv.create_text(W // 2, int(H * 0.9), text=f"v{APP_VERSION}", fill=MUTED, font=(self.F.mono, 9))
        sp._photos = photos
        total = 44
        state = {"i": 0}

        def step():
            i = state["i"]
            state["i"] += 1
            try:
                cv.itemconfig(img_id, image=photos[i % len(photos)])
                alpha = min(1.0, i / 6) if i < total - 8 else max(0.0, (total - i) / 8)
                sp.attributes("-alpha", alpha)
            except tk.TclError:
                pass
            if i >= total:
                sp.destroy()
                self.splashing = False
                self.show_window()
                return
            sp.after(45, step)
        step()

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
                messagebox.showinfo(APP_NAME, T("Chưa cấu hình GITHUB_REPO trong mã nguồn."), parent=self.win)
            return
        if self.checking_update:
            return
        self.checking_update = True
        self.upd_label.configure(text=T("Đang kiểm tra cập nhật..."))

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
                self.upd_label.configure(text=T("Bạn đang dùng phiên bản mới nhất."))
                if manual:
                    messagebox.showinfo(APP_NAME, T("Bạn đang dùng phiên bản mới nhất") + f" ({APP_VERSION}).",
                                        parent=self.win)
                return
            self.upd_label.configure(text=T("Có phiên bản mới: ") + info["version"], text_color=ACCENT)
            if not manual and info["version"] == self.cfg["skipped_version"]:
                return
            if self.win.state() == "withdrawn":
                self.pending_update = info
                try:
                    self.icon.notify(T("Đã có EzCursor {v}. Mở EzCursor để cập nhật.").format(v=info["version"]), APP_NAME)
                except Exception:
                    pass
            else:
                self.show_update_dialog(info, manual)
        elif kind == "update_error":
            self.checking_update = False
            self.upd_label.configure(text=T("Không kiểm tra được cập nhật."))
            if manual:
                messagebox.showerror(APP_NAME, T("Không kiểm tra được cập nhật.\nHãy kiểm tra kết nối mạng.") + f"\n\n{data}",
                                     parent=self.win)
        elif kind == "dl_progress":
            self.dl_bar.set(data / 100)
            self.dl_label.configure(text=T("Đang tải...") + f" {data:.0f}%")
        elif kind == "dl_done":
            self.dl_label.configure(text=T("Đang cài đặt, EzCursor sẽ tự mở lại sau giây lát..."))
            try:
                subprocess.Popen([data, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH"])
            except Exception as e:
                messagebox.showerror(APP_NAME, T("Không chạy được bộ cài:") + f"\n{e}", parent=self.upd_dialog)
                return
            self.ov.after(200, self.quit)
        elif kind == "dl_error":
            self.btn_update.configure(state="normal")
            self.dl_label.configure(text=T("Tải về thất bại."))
            messagebox.showerror(APP_NAME, T("Tải bản cập nhật thất bại:") + f"\n{data}", parent=self.upd_dialog)

    def show_update_dialog(self, info, manual):
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        d.title(f"{APP_NAME} - " + T("Cập nhật"))
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
        ctk.CTkLabel(title, text=T("   (bạn đang dùng {v})").format(v=APP_VERSION), font=self.F.b(12),
                     text_color=TEXT2).pack(side="left")
        self.caps(frm, "CÓ GÌ MỚI").pack(anchor="w")
        tb = ctk.CTkTextbox(frm, width=520, height=200, fg_color=CARD, border_color=BORDER, border_width=1,
                            corner_radius=10, font=self.F.b(13), text_color=TEXT, wrap="word")
        tb.insert("1.0", info["notes"].strip() or T("(không có ghi chú)"))
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
            self.btn_update = ctk.CTkButton(bf, text=T("CẬP NHẬT NGAY"), command=lambda: self.start_download(info),
                                            height=42, corner_radius=10, fg_color=ACCENT,
                                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        else:
            self.btn_update = ctk.CTkButton(bf, text=T("MỞ TRANG TẢI VỀ"), command=lambda: webbrowser.open(info["page"]),
                                            height=42, corner_radius=10, fg_color=ACCENT,
                                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        self.btn_update.pack(side="right")
        ctk.CTkButton(bf, text=T("Để sau"), command=d.destroy, height=42, width=90, corner_radius=10,
                      fg_color="transparent", hover_color="#161A23", border_width=1, border_color=BORDER,
                      text_color=TEXT2, font=self.F.b(13, strong=True)).pack(side="right", padx=8)
        if not manual:
            def skip():
                self.cfg["skipped_version"] = info["version"]
                self.save()
                d.destroy()
            ctk.CTkButton(bf, text=T("Bỏ qua phiên bản này"), command=skip, height=42, corner_radius=10,
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
                self.pcv.itemconfig(self.ping, outline=mix(self.glow_color(), FIELD, min(1, phase * 1.05)))
                if f % 3 == 0:
                    pt = wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    self.pcv.itemconfig(self.coord_txt, text=f"X {pt.x} · Y {pt.y}")
            if self.logo_ctk and f % 2 == 0:
                self.logo_lbl.configure(image=self.logo_ctk[(f // 2) % len(self.logo_ctk)])
            if self.tab == "cursor" and self.preview_photos and f % 3 == 0:
                self.pcv.itemconfig(self.pimg_id, image=self.preview_photos[(f // 3) % len(self.preview_photos)])
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
        was_shell = self.shell_open
        self.set_active(self.compute_active())
        if was_shell != self.shell_open:
            self.update_status()
        if self.active:
            self.move_overlay()
        self.ov.after(4, self.tick)

    def quit(self):
        cleanup()
        self.ovl.destroy()
        self.fxw.destroy()
        self.save()
        try:
            self.icon.stop()
        except Exception:
            pass
        self.ov.destroy()


APP_USER_MODEL_ID = "Columbustrade.EzCursor"


def main():
    try:   # để taskbar nhận EzCursor là một ứng dụng riêng, dùng icon của EzCursor
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass
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

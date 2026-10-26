# -*- coding: utf-8 -*-
"""
EzCursor - con trỏ chuột tùy chỉnh cho game có con trỏ riêng (vd: Last Epoch)

- Giao diện Neon HUD (CustomTkinter)
- Tab "Ứng dụng": chọn ứng dụng đang chạy để áp dụng con trỏ, bấm Áp dụng
- Giao diện tiếng Việt / tiếng Anh (tab Tùy chọn > Ngôn ngữ)
- Bấm X: thu nhỏ xuống khay hệ thống. Thoát hẳn: menu khay hoặc Ctrl+Alt+Q
Phím tắt: Ctrl+Alt+H bật/tắt, Ctrl+Alt+R đổi con trỏ, Ctrl+Alt+F tìm con trỏ, Ctrl+Alt+1..5 đổi màu, Ctrl+Alt+Q thoát
Cài đặt lưu tại %APPDATA%\\EzCursor
"""

import atexit
import collections.abc
import colorsys
import ctypes
import hashlib
import io
import json
import logging
import logging.handlers
import math
import os
import platform
import random
import queue
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
import tkinter as tk
import winreg
from ctypes import wintypes
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
import pystray
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageSequence, ImageTk

APP_NAME = "EzCursor"
APP_VERSION = "2.2.0"

# ======== SỬA DÒNG NÀY thành repository GitHub của bạn (tên-tài-khoản/tên-repo) ========
GITHUB_REPO = "ezcursor/EzCursor"
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
VK_CONTROL, VK_MENU, VK_SHIFT = 0x11, 0x12, 0x10
ERROR_ALREADY_EXISTS = 183
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

mag = ctypes.windll.magnification
mag.MagInitialize()
try:          # luôn hiện con trỏ thật khi khởi động (phòng lần chạy trước bị tắt ngang)
    mag.MagShowSystemCursor(True)
except Exception:
    pass
_cursor_shown = True
log = logging.getLogger("ezcursor")


def show_real_cursor(show):
    global _cursor_shown
    show = bool(show)
    if show != _cursor_shown:
        mag.MagShowSystemCursor(show)
        _cursor_shown = show


# ---------------------------------------------------------------- Chế độ "Con trỏ thật" (thay con trỏ Windows)
REAL_CURSOR_MODE = False      # chế độ "Con trỏ thật" đang ẩn (để dành); True = hiện lựa chọn trong tab Tùy chọn
SPI_SETCURSORS = 0x0057
IMAGE_CURSOR = 2
SYS_CURSOR_IDS = (32512, 32513, 32514, 32515, 32516, 32648, 32649, 32650, 32651)   # mũi tên, chữ I, chờ, thập...
_sys_applied = False


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


_gdi = ctypes.windll.gdi32
try:
    _gdi.CreateDIBSection.restype = ctypes.c_void_p
    _gdi.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                      ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint]
    _gdi.CreateBitmap.restype = ctypes.c_void_p
    _gdi.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    _gdi.DeleteObject.argtypes = [ctypes.c_void_p]
    user32.CreateIconIndirect.restype = ctypes.c_void_p
    user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
    user32.CopyImage.restype = ctypes.c_void_p
    user32.CopyImage.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetSystemCursor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    user32.DestroyCursor.argtypes = [ctypes.c_void_p]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
except Exception:
    pass


def make_hcursor(im, hot):
    """Ảnh RGBA -> HCURSOR 32 bit có kênh trong suốt (tối đa 256 px)."""
    im = im.convert("RGBA")
    if max(im.size) > 256:
        k = 256 / max(im.size)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        hot = (round(hot[0] * k), round(hot[1] * k))
    w, h = im.size
    bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1,
                           biBitCount=32, biCompression=0)
    bits = ctypes.c_void_p()
    hdc = user32.GetDC(None)
    color = _gdi.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    user32.ReleaseDC(None, hdc)
    if not color or not bits:
        raise OSError("CreateDIBSection")
    data = im.tobytes("raw", "BGRA")
    ctypes.memmove(bits, data, len(data))
    stride = (w + 15) // 16 * 2
    zeros = ctypes.create_string_buffer(stride * h)
    mask = _gdi.CreateBitmap(w, h, 1, 1, zeros)
    info = ICONINFO(False, max(0, min(w - 1, int(hot[0]))), max(0, min(h - 1, int(hot[1]))), mask, color)
    hc = user32.CreateIconIndirect(ctypes.byref(info))
    _gdi.DeleteObject(color)
    _gdi.DeleteObject(mask)
    if not hc:
        raise OSError("CreateIconIndirect")
    return hc


def set_system_cursors(hcur):
    """Đặt con trỏ Windows (mũi tên, chữ I, chờ...) thành hcur. SetSystemCursor hủy handle nên mỗi lần dùng bản sao."""
    global _sys_applied
    if not _sys_applied:
        try:
            SYS_FLAG.write_text("1", encoding="utf-8")
        except OSError:
            pass
    _sys_applied = True
    ok, errs = 0, []
    for oid in SYS_CURSOR_IDS:
        h = user32.CopyImage(hcur, IMAGE_CURSOR, 0, 0, 0)
        if not h:
            errs.append(f"copy {oid}:{kernel32.GetLastError()}")
            continue
        if user32.SetSystemCursor(h, oid):
            ok += 1
        else:
            errs.append(f"set {oid}:{kernel32.GetLastError()}")
    return ok, errs


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", ctypes.c_void_p),
                ("ptScreenPos", wintypes.POINT)]


try:
    user32.LoadCursorW.restype = ctypes.c_void_p
    user32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
except Exception:
    pass
_shared_cursors = None


def current_cursor():
    """(đang hiện?, handle con trỏ đang dùng)."""
    ci = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
    if not user32.GetCursorInfo(ctypes.byref(ci)):
        return True, None
    return bool(ci.flags & 1), ci.hCursor


def is_system_cursor(h):
    """Con trỏ đang hiện có phải con trỏ chung của Windows (mũi tên, chữ I...) – tức là con trỏ EzCursor đã thay?"""
    global _shared_cursors
    if _shared_cursors is None:
        _shared_cursors = {user32.LoadCursorW(None, ctypes.c_void_p(oid)) for oid in SYS_CURSOR_IDS} - {None, 0}
    return h in _shared_cursors


def restore_system_cursors(force=False):
    """Trả lại bộ con trỏ Windows của người dùng."""
    global _sys_applied
    if not (_sys_applied or force):
        return
    try:
        user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
    except Exception:
        pass
    _sys_applied = False
    try:
        SYS_FLAG.unlink()
    except OSError:
        pass


try:          # đồng hồ hẹn giờ của Windows chính xác tới 1 ms (mặc định ~15,6 ms làm vòng lặp chạy chậm)
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass


def cleanup():
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass
    try:
        restore_system_cursors()
    except Exception:
        pass
    try:
        mag.MagShowSystemCursor(True)
        mag.MagUninitialize()
    except Exception:
        pass


atexit.register(cleanup)


def emergency_cursor():
    """Trả con trỏ thật ngay lập tức, dùng khi có lỗi."""
    global _cursor_shown
    try:
        mag.MagShowSystemCursor(True)
        _cursor_shown = True
    except Exception:
        pass
    try:
        restore_system_cursors()
    except Exception:
        pass


def _excepthook(exc_type, exc, tb):
    emergency_cursor()
    try:
        log.critical("Lỗi chưa xử lý:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def _thread_excepthook(args):
    emergency_cursor()
    try:
        log.error("Lỗi trong luồng %s:\n%s", getattr(args.thread, "name", "?"),
                  "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
    except Exception:
        pass


sys.excepthook = _excepthook
threading.excepthook = _thread_excepthook


def mouse_buttons():
    """(chuột trái, chuột phải) đang giữ, theo nút logic (tính cả khi người dùng đổi nút chuột)."""
    l, r = bool(key_down(0x01)), bool(key_down(0x02))
    return (r, l) if user32.GetSystemMetrics(23) else (l, r)     # SM_SWAPBUTTON


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
QUIT_FLAG = APP_DIR / "quit.flag"
SYS_FLAG = APP_DIR / "syscursor.flag"     # có file này = con trỏ Windows đang bị EzCursor thay
if SYS_FLAG.exists():
    restore_system_cursors(force=True)
MY_DIR = APP_DIR / "my_cursors"        # "Con trỏ của bạn" (1.9.0)
MY_EXTS = {".png", ".gif", ".webp", ".ico", ".cur", ".ani", ".bmp", ".jpg", ".jpeg"}   # bộ cài dùng để yêu cầu thoát

TRANSPARENT = "#010101"
PRESET_COLORS = ["#ff2828", "#28ff28", "#00c8ff", "#ffe600", "#ff00dc"]
SHAPES = ["EzDrop", "EzPink", "ez_crosshair", "ez_sword", "ez_crystal", "ez_gem", "ez_rune", "ez_orb", "ez_flame", "ez_spear", "ez_feather", "ez_star", "ez_shot", "ez_neon", "Mũi tên", "Vòng tròn", "Dấu thập", "Chấm tròn", "Kim cương", "Ảnh tải lên", "Bibata"]
HOTSPOTS = ["Giữa ảnh", "Góc trên trái", "Theo file"]
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
    "own_theme": "original",
    "hold_left": False,
    "hold_left_color": "#22D3EE",
    "hold_right": False,
    "hold_right_color": "#FFD60A",
    "ombre": False,                                     # dải màu ombre thay cho một màu
    "ombre_colors": ["#FF2E93", "#FF8A3D", "#FFD60A"],
    "ombre_anim": False,                                # dải màu chạy chầm chậm
    "ombre_speed": "mid",
    "hide_real": True,
    "enabled": True,
    "all_apps": False,
    "apps": [],
    "tray_hint_shown": False,
    "auto_check_update": True,
    "last_update_check": 0,
    "skipped_version": "",
    "language": "vi",
    "dpi_scale": False,
    "find_shake": True,
    "catalog_got": {},        # con trỏ đã tải từ kho trực tuyến: {id: tên file trong my_cursors}
    "made_cursors": {},       # con trỏ tự tạo: {tên file trong my_cursors: thông số} để mở lại sửa
    "sys_skip": [],            # game tự đặt con trỏ riêng -> dùng Lớp phủ dù đang ở chế độ Con trỏ thật
    "cursor_mode": "overlay",  # "overlay" (lớp phủ, nhiều hiệu ứng) / "system" (con trỏ thật, không độ trễ)
    "predict": True,           # đoán trước vị trí con trỏ theo tốc độ chuột (bù ~nửa khung hình)
    "keep_taskbar": True,      # rê chuột xuống taskbar vẫn dùng con trỏ EzCursor
    "setup_done": False,      # đã qua màn hình thiết lập lần đầu
    "favorites": [],          # con trỏ yêu thích: mã hình, "bib:<tên>" hoặc "my:<tên file>"
    "profiles": [],      # hồ sơ riêng: [{"name": ..., "exes": [...], "style": {...}}]
    "hotkeys": {
        "toggle": {"mods": ["ctrl", "alt"], "vk": 0x48},   # H
        "shape": {"mods": ["ctrl", "alt"], "vk": 0x52},    # R
        "quit": {"mods": ["ctrl", "alt"], "vk": 0x51},     # Q
        "find": {"mods": ["ctrl", "alt"], "vk": 0x46},     # F
        "color": {"mods": ["ctrl", "alt"]},                # + phím số 1..5
    },
}

# Game ARPG phổ biến: (tên hiển thị, các file chạy có thể gặp)
ARPG_GAMES = [
    ("Last Epoch", ["Last Epoch.exe"]),
    ("Path of Exile 1 / 2", ["PathOfExile.exe", "PathOfExileSteam.exe", "PathOfExile_x64.exe",
                             "PathOfExile_x64Steam.exe"]),
    ("Diablo IV", ["Diablo IV.exe"]),
    ("Diablo III", ["Diablo III64.exe", "Diablo III.exe"]),
    ("Diablo II: Resurrected", ["D2R.exe"]),
    ("Grim Dawn", ["Grim Dawn.exe"]),
    ("Torchlight II", ["Torchlight2.exe"]),
    ("Titan Quest", ["TQ.exe"]),
    ("Lost Ark", ["LOSTARK.exe"]),
]


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


def default_cfg():
    return json.loads(json.dumps(DEFAULT_CFG))     # bản sao sâu


# Các cài đặt thuộc về "kiểu con trỏ": mỗi hồ sơ game có một bộ riêng
STYLE_KEYS = ("color", "shape", "size", "image", "hotspot", "tint_image", "glow", "cursor_sparkle",
              "fx_trail", "fx_click", "fx_color", "fx_density",
              "bibata_cursor", "bibata_theme", "bibata_style", "bibata_hand", "own_theme",
              "hold_left", "hold_left_color", "hold_right", "hold_right_color",
              "ombre", "ombre_colors", "ombre_anim", "ombre_speed")


def clean_style(cfg):
    """Sửa các giá trị kiểu con trỏ không hợp lệ (dùng cho cấu hình chính lẫn từng hồ sơ)."""
    for k in STYLE_KEYS:
        if k not in cfg:
            cfg[k] = DEFAULT_CFG[k]
    if cfg["shape"] not in SHAPES:
        cfg["shape"] = DEFAULT_CFG["shape"]
    if cfg["hotspot"] not in HOTSPOTS:
        cfg["hotspot"] = HOTSPOTS[0]
    cfg["size"] = max(24, min(160, int(cfg["size"])))
    if cfg["bibata_theme"] not in ("amber", "classic", "ice", "custom"):
        cfg["bibata_theme"] = "amber"
    if cfg["own_theme"] not in ("original", "custom"):
        cfg["own_theme"] = "original"
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
    for k in ("color", "hold_left_color", "hold_right_color"):
        if not isinstance(cfg[k], str) or len(cfg[k]) != 7 or not cfg[k].startswith("#"):
            cfg[k] = DEFAULT_CFG[k]
    for k in ("tint_image", "glow", "cursor_sparkle", "hold_left", "hold_right", "ombre", "ombre_anim"):
        cfg[k] = bool(cfg[k])
    oc = cfg["ombre_colors"]
    oc = [x for x in oc if isinstance(x, str) and len(x) == 7 and x.startswith("#")] if isinstance(oc, list) else []
    cfg["ombre_colors"] = oc[:5] if len(oc) >= 2 else list(DEFAULT_CFG["ombre_colors"])
    if cfg["ombre_speed"] not in OMBRE_SPEEDS:
        cfg["ombre_speed"] = "mid"
    if cfg["image"] and not Path(cfg["image"]).exists():
        name = Path(cfg["image"]).name
        alt = next((d / name for d in (MY_DIR, APP_DIR) if (d / name).exists()), None)
        cfg["image"] = str(alt) if alt else ""
    return cfg


# Kho con trỏ trực tuyến (2.0): danh sách nằm trên website, thêm con trỏ mới không cần phát hành app
CATALOG_URL = "https://ezcursor.github.io/catalog/catalog.json"
CAT_DIR = APP_DIR / "catalog"            # bộ nhớ đệm: danh sách + ảnh nhỏ
CAT_EXTS = {".cur", ".ani", ".png", ".gif"}
CAT_MAX = 3 * 1024 * 1024


def http_get(url, limit):
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise ValueError("URL không hợp lệ")
    req = urllib.request.Request(url, headers={"User-Agent": f"EzCursor/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=12) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File quá lớn")
    return data


def clean_catalog(data):
    """Chỉ giữ các mục hợp lệ của catalog.json (tên file đơn giản, đúng định dạng, có mã kiểm tra)."""
    out = []
    for e in data.get("cursors", []) if isinstance(data, dict) else []:
        try:
            cid, f, th = e["id"], e["file"], e["thumb"]
            ok = (re.fullmatch(r"[a-z0-9_-]{1,40}", cid) and re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", f)
                  and re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", th) and ".." not in f + th
                  and Path(f).suffix.lower() in CAT_EXTS and th.lower().endswith(".png")
                  and re.fullmatch(r"[0-9a-f]{64}", e["sha256"]) and 0 < int(e["size"]) <= CAT_MAX)
            if not ok:
                continue
            name = e.get("name")
            name = name if isinstance(name, dict) else {"vi": str(name or cid)}
            out.append({"id": cid, "file": f, "thumb": th, "sha256": e["sha256"], "size": int(e["size"]),
                        "name": {k: str(v)[:40] for k, v in name.items()}, "added": str(e.get("added", ""))[:10]})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def catalog_name(e):
    return e["name"].get(LANG) or e["name"].get("vi") or next(iter(e["name"].values()), e["id"])


def my_cursor_files():
    """Các con trỏ người dùng đã thêm, mới nhất ở cuối."""
    try:
        files = [f for f in MY_DIR.iterdir() if f.is_file() and f.suffix.lower() in MY_EXTS]
    except OSError:
        return []
    return sorted(files, key=lambda f: f.stat().st_mtime)


def unique_my_path(name):
    stem = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in Path(name).stem).strip() or "cursor"
    ext = Path(name).suffix.lower()
    dest, i = MY_DIR / f"{stem}{ext}", 2
    while dest.exists():
        dest, i = MY_DIR / f"{stem}-{i}{ext}", i + 1
    return dest


def migrate_my_cursors(cfg):
    """Đưa ảnh tải lên ở các bản trước (custom*.*) vào "Con trỏ của bạn" và sửa đường dẫn trong cài đặt."""
    try:
        MY_DIR.mkdir(parents=True, exist_ok=True)
        moved = {}
        for f in APP_DIR.glob("custom*.*"):
            if f.is_file() and f.suffix.lower() in MY_EXTS:
                dest = unique_my_path(f.name)
                shutil.move(str(f), str(dest))
                moved[f.name.lower()] = str(dest)
        if not moved:
            return
        styles = [cfg] + [pr.get("style", {}) for pr in cfg.get("profiles", []) if isinstance(pr, dict)]
        for st in styles:
            img = st.get("image") or ""
            if img and Path(img).name.lower() in moved:
                st["image"] = moved[Path(img).name.lower()]
    except Exception:
        pass


def load_cfg():
    cfg = default_cfg()
    raw = {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cfg.update(raw)
    except Exception:
        pass
    if not isinstance(raw, dict) or "setup_done" not in raw:     # đã dùng bản cũ thì không cần thiết lập lại
        cfg["setup_done"] = bool(raw)
    try:
        clean_style(cfg)
    except Exception:
        for k in STYLE_KEYS:
            cfg[k] = DEFAULT_CFG[k]
    profiles = []
    for pr in cfg.get("profiles") if isinstance(cfg.get("profiles"), list) else []:
        try:
            exes = [e for e in pr["exes"] if isinstance(e, str) and e]
            if not exes or not isinstance(pr.get("name"), str):
                continue
            st = {k: cfg[k] for k in STYLE_KEYS}
            st.update({k: v for k, v in pr.get("style", {}).items() if k in STYLE_KEYS})
            profiles.append({"name": pr["name"], "exes": exes, "style": clean_style(st)})
        except Exception:
            continue
    cfg["profiles"] = profiles
    cfg["dpi_scale"] = bool(cfg.get("dpi_scale"))
    cfg["find_shake"] = bool(cfg.get("find_shake", True))
    sk = cfg.get("sys_skip") if isinstance(cfg.get("sys_skip"), list) else []
    cfg["sys_skip"] = [x for x in sk if isinstance(x, str)][:50]
    cfg["keep_taskbar"] = bool(cfg.get("keep_taskbar", True))
    cfg["predict"] = bool(cfg.get("predict", True))
    if cfg.get("cursor_mode") not in ("overlay", "system"):
        cfg["cursor_mode"] = "overlay"
    made = cfg.get("made_cursors") if isinstance(cfg.get("made_cursors"), dict) else {}
    cfg["made_cursors"] = {k: v for k, v in made.items() if isinstance(k, str) and isinstance(v, dict)}
    got = cfg.get("catalog_got") if isinstance(cfg.get("catalog_got"), dict) else {}
    cfg["catalog_got"] = {k: v for k, v in got.items() if isinstance(k, str) and isinstance(v, str)}
    favs = cfg.get("favorites") if isinstance(cfg.get("favorites"), list) else []
    cfg["favorites"] = list(dict.fromkeys(f for f in favs if isinstance(f, str) and f))[:60]
    migrate_my_cursors(cfg)
    cfg["hotkeys"] = clean_hotkeys(cfg.get("hotkeys"))
    if cfg["language"] not in dict(LANGUAGES):
        cfg["language"] = "vi"
    if not isinstance(cfg["apps"], list):
        cfg["apps"] = list(DEFAULT_CFG["apps"])
    return cfg


class ProfileCfg(collections.abc.MutableMapping):
    """Cấu hình dùng trong app: các khóa kiểu con trỏ đọc/ghi vào hồ sơ đang chọn (target),
    các khóa còn lại đọc/ghi vào cấu hình chính (base). Hồ sơ Mặc định chính là base."""

    def __init__(self, base):
        self.base = base
        self.target = base

    def __getitem__(self, k):
        if k in STYLE_KEYS and self.target is not self.base:
            return self.target.get(k, self.base[k])
        return self.base[k]

    def __setitem__(self, k, v):
        (self.target if k in STYLE_KEYS else self.base)[k] = v

    def __delitem__(self, k):
        del self.base[k]

    def __iter__(self):
        return iter(self.base)

    def __len__(self):
        return len(self.base)


def slug(text):
    keep = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    return "-".join(x for x in keep.split("-") if x)[:40] or "game"


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
    # 1.5.0
    "Theo file": "From file", "Phóng theo tỉ lệ màn hình": "Scale with display",
    "GỢI Ý: GAME ARPG PHỔ BIẾN": "SUGGESTED: POPULAR ARPGS", " GỢI Ý ": " SUGGESTED ",
    "●  FULLSCREEN": "●  FULLSCREEN",
    "Game đang ở Fullscreen. Hãy chuyển sang Borderless hoặc Windowed.":
        "The game is in Fullscreen. Switch it to Borderless or Windowed.",
    "Game đang chạy Fullscreen nên EzCursor không vẽ được con trỏ. "
    "Hãy chuyển game sang Borderless hoặc Windowed trong phần cài đặt đồ họa.":
        "The game is running in Fullscreen, so EzCursor can't draw the cursor. "
        "Switch the game to Borderless or Windowed in its graphics settings.",
    "Ảnh hoặc con trỏ": "Images or cursors", "Con trỏ Windows": "Windows cursors",
    "Mặc định": "Defaults", "Bấm vào một ô để đổi phím": "Click a box to change it",
    "Đổi phím tắt": "Change hotkey", "Nhấn tổ hợp phím mới": "Press the new key combination",
    "Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím số từ 1 đến 5.":
        "Hold Ctrl or Alt (optionally with Shift) and press a number key from 1 to 5.",
    "Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím chữ, số hoặc F1–F12.":
        "Hold Ctrl or Alt (optionally with Shift) and press a letter, number or F1–F12 key.",
    "Bấm Esc để hủy.": "Press Esc to cancel.", "Cần giữ Ctrl hoặc Alt.": "Hold Ctrl or Alt.",
    "Đổi màu dùng các phím số 1–5.": "Color changes use number keys 1–5.",
    "Trùng với phím của: ": "Already used by: ",
    # 1.6.0
    "Đang chỉnh": "Editing", "Mặc định (mọi game)": "Default (all games)",
    # 1.9.0
    "Đổi con trỏ": "Change cursor", "Hình cơ bản": "Basic shapes", "Con trỏ của bạn": "Your cursors",
    "(chưa có)": "(none yet)", "Hồ sơ": "Profile", "Áp cho: {n}": "Applies to: {n}",
    "Yêu thích": "Favorites", "Thêm vào Yêu thích": "Add to favorites", "Bỏ khỏi Yêu thích": "Remove from favorites",
    "Bấm ☆ để thêm vào Yêu thích. Ctrl+Alt+R sẽ chỉ đổi giữa các con trỏ yêu thích.":
        "Click ☆ to add a favorite. Ctrl+Alt+R then cycles through your favorites only.",
    "THIẾT LẬP NHANH": "QUICK SETUP", "Bước {i} / 3": "Step {i} / 3", "Bỏ qua": "Skip", "Quay lại": "Back",
    "Tiếp tục": "Next", "Bắt đầu": "Let's go",
    "Bạn chơi game nào?": "Which games do you play?",
    "EzCursor chỉ hiện con trỏ khi các game này đang mở. Có thể đổi sau ở tab Ứng dụng.":
        "EzCursor only shows its cursor while these games are open. You can change this later in the Apps tab.",
    "Chọn con trỏ": "Pick a cursor",
    "Chọn con trỏ bạn thích. Bộ sưu tập còn bộ Bibata và chỗ thêm con trỏ của riêng bạn.":
        "Pick the cursor you like. The Library also has the Bibata set and room for your own cursors.",
    "Nhỏ": "Small", "Vừa": "Medium", "Lớn": "Large",
    "Sẵn sàng!": "All set!",
    "Mở game là con trỏ mới sẽ hiện. Vài phím tắt nên nhớ:": "Open your game and the new cursor appears. A few handy hotkeys:",
    "Đổi con trỏ (giữa các con trỏ yêu thích)": "Change cursor (between favorites)",
    "Tìm con trỏ (hoặc lắc chuột)": "Find cursor (or shake the mouse)",
    "EzCursor chạy ở khay hệ thống. Chuột phải vào icon để đổi nhanh con trỏ hoặc hồ sơ.":
        "EzCursor lives in the system tray. Right-click its icon to quickly change cursor or profile.",
    "Game": "Games", "Mọi ứng dụng": "All applications", "(chưa chọn)": "(none selected)",
    "Trực tuyến": "Online", "Làm mới": "Refresh", "Đang tải danh sách…": "Loading the list…",
    "{n} con trỏ · Bấm để tải về, con trỏ sẽ nằm trong mục Của bạn.":
        "{n} cursors · Click to download; it will be added to Yours.",
    "Không kết nối được kho trực tuyến. Kiểm tra mạng rồi bấm Làm mới.":
        "Couldn't reach the online catalog. Check your connection and click Refresh.",
    "Đang xem danh sách lưu lần trước (chưa kết nối được).": "Showing the last saved list (offline).",
    "Tải về": "Download", "Đang tải…": "Downloading…", "✓ Đã có": "✓ Added", "MỚI": "NEW",
    "Không tải được con trỏ:": "Couldn't download the cursor:",
    "File không khớp mã kiểm tra": "Checksum mismatch", "File con trỏ bị lỗi": "The cursor file is damaged",
    "File quá lớn": "File too large",
    "MÀU OMBRE": "OMBRE", "  Chuyển động": "  Animate", "Chậm": "Slow", "Nhanh": "Fast",
    "Hoàng hôn": "Sunset", "Đại dương": "Ocean", "Lửa": "Fire", "Độc dược": "Toxic", "Băng giá": "Frost",
    "Hư không": "Void", "Cầu vồng": "Rainbow", "Tự chọn": "Custom", "Tự chọn màu ombre": "Custom ombre",
    "Màu 1 ở mũi con trỏ, màu cuối ở đuôi.": "Color 1 is at the cursor tip, the last color at the tail.",
    "Dùng 3 màu": "Use 3 colors", "Dùng dải màu này": "Use these colors", "Hủy": "Cancel",
    "✦ Tạo con trỏ": "✦ Create cursor", "Tạo con trỏ": "Create cursor", "TẠO CON TRỎ": "CREATE A CURSOR",
    "Chọn hình, chỉnh dáng, màu và viền. Con trỏ được lưu vào mục Của bạn.":
        "Pick a shape, then tune its form, colors and outline. It's saved to Yours.",
    "Bấm vào hình để đặt điểm click": "Click the image to set the click point",
    "Điểm click tự động": "Auto click point", "KÍCH THƯỚC THẬT": "ACTUAL SIZE", "HÌNH DÁNG": "SHAPE",
    "DÁNG": "FORM", "Độ rộng": "Width", "Độ dài đuôi": "Tail length", "Độ dày nét": "Thickness", "Bo góc": "Roundness",
    "Xoay": "Rotation", "Khe hở": "Gap", "TÔ MÀU": "FILL", "Một màu": "Solid", "Kính mờ": "Glass", "VIỀN": "OUTLINE",
    "Viền trong": "Inner outline", "Viền ngoài": "Outer outline", "CHI TIẾT": "DETAILS",
    "Chấm sáng ở mũi": "Tip dot", "Vệt sáng": "Shine", "Bóng đổ": "Shadow", "Tên": "Name",
    "Con trỏ của tôi": "My cursor", "Lưu vào Của bạn": "Save to Yours", "Không lưu được con trỏ:": "Couldn't save the cursor:",
    "Sửa con trỏ này": "Edit this cursor",
    "Nhọn": "Sharp", "Bo tròn": "Rounded", "Mảnh": "Slim", "Pha lê": "Shard", "Giọt nước": "Droplet",
    "Tam giác": "Triangle", "Chấm": "Dot", "Vòng": "Ring",
    "Chưa có con trỏ nào. Tự tạo một con trỏ, hoặc bấm \"+ Thêm con trỏ\" để thêm ảnh PNG, GIF hay file .cur, .ani.":
        "No cursors yet. Create one, or click \"+ Add cursor\" to add a PNG, GIF, .cur or .ani file.",
    "{g} dùng con trỏ riêng của game nên chế độ Con trỏ thật không đổi được. EzCursor đã chuyển sang Lớp phủ cho game này.":
        "{g} uses its own cursor, so Real cursor mode can't replace it. EzCursor switched to Overlay for this game.",
    "Game này dùng con trỏ riêng và đang chạy Fullscreen nên EzCursor không thể hiện con trỏ. Hãy chuyển game sang Borderless hoặc Windowed.":
        "This game uses its own cursor and runs in exclusive Fullscreen, so EzCursor can't show its cursor. Switch the game to Borderless or Windowed.",
    "Giữ con trỏ trên thanh taskbar": "Keep cursor on the taskbar",
    "Rê chuột xuống taskbar vẫn dùng con trỏ EzCursor.": "Keep the EzCursor cursor when you move over the taskbar.",
    "Đoán trước vị trí con trỏ": "Predict cursor position",
    "Bù thêm nửa khung hình khi rê nhanh; có thể trượt nhẹ khi đổi hướng.":
        "Gains half a frame on fast moves; may overshoot slightly when you change direction.",
    "Chế độ con trỏ": "Cursor mode", "Lớp phủ": "Overlay", "Con trỏ thật": "Real cursor",
    "Không độ trễ, chạy cả Fullscreen. Không có lấp lánh, ombre chuyển động.":
        "Zero lag, works in Fullscreen too. No sparkle or animated ombre.",
    "Đủ hiệu ứng. Game cần chạy Borderless hoặc Windowed.": "All effects. The game must run Borderless or Windowed.",
    "Game đang chạy Fullscreen nên EzCursor không vẽ được con trỏ. Hãy chuyển game sang Borderless hoặc Windowed, "
    "hoặc bật chế độ \"Con trỏ thật\" trong tab Tùy chọn.":
        "The game is running in exclusive Fullscreen, so EzCursor can't draw its cursor. Switch the game to "
        "Borderless or Windowed, or turn on \"Real cursor\" mode in the Options tab.",
    "Của bạn": "Yours", "Tô màu": "Tinted", "+ Thêm con trỏ": "+ Add cursor", "Xóa con trỏ này": "Delete this cursor",
    "Xóa con trỏ \"{n}\" khỏi bộ sưu tập?": "Remove the cursor \"{n}\" from your library?",
    "Chưa có con trỏ nào. Bấm \"+ Thêm con trỏ\" để thêm ảnh PNG, GIF hoặc file con trỏ .cur, .ani.":
        "No cursors yet. Click \"+ Add cursor\" to add a PNG, GIF or .cur / .ani cursor file.",
    "Tìm con trỏ": "Find cursor", "Lắc chuột để tìm": "Shake to find",
    # 1.8.0
    "Bộ EzCursor": "EzCursor set", "Màu gốc": "Original",
    "Tâm ngắm Neon": "Neon Crosshair",
    "Mũi kiếm": "Blade",
    "Mũi tên Pha lê": "Crystal Arrow",
    "Viên ngọc": "Gem",
    "Ký tự Rune": "Rune",
    "Cầu năng lượng": "Energy Orb",
    "Ngọn lửa": "Flame",
    "Mũi giáo": "Spear",
    "Lông vũ": "Feather",
    "Ngôi sao": "Star",
    "Mũi tên Bắn": "Arrow Shot",
    "Mũi tên Neon": "Neon Arrow",
    # 1.7.0
    "Viền khi giữ chuột": "Outline while holding", "Trái": "Left", "Phải": "Right",
    "Chọn màu viền": "Choose outline color", "Mở thư mục log": "Open log folder",
    "EzCursor gặp lỗi liên tục nên đã tạm tắt con trỏ để bạn dùng chuột bình thường. "
    "Hãy mở lại EzCursor; chi tiết lỗi nằm trong file ezcursor.log.":
        "EzCursor kept hitting errors, so it turned its cursor off to keep your mouse usable. "
        "Please reopen EzCursor; details are in ezcursor.log.",
    "+ Hồ sơ riêng": "+ Own profile", "✓ Hồ sơ riêng": "✓ Own profile", "Hồ sơ: ": "Profile: ",
    "Xóa hồ sơ riêng \"{n}\"? Game này sẽ dùng lại kiểu Mặc định.":
        "Delete the profile \"{n}\"? This game will go back to the Default style.",
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


# ---------------------------------------------------------------- Màu ombre (2.1.0)
OMBRE_PRESETS = [   # (mã, tên, các màu từ mũi ra đuôi)
    ("sunset", "Hoàng hôn", ["#FF2E93", "#FF8A3D", "#FFD60A"]),
    ("ez", "EzCursor", ["#2EE59D", "#2F80FF", "#FF2E93"]),
    ("ocean", "Đại dương", ["#22D3EE", "#3B7BF9", "#8B5CF6"]),
    ("fire", "Lửa", ["#FFD60A", "#FF6A00", "#E01E37"]),
    ("toxic", "Độc dược", ["#E4FF3B", "#7CF03B", "#14B8A6"]),
    ("frost", "Băng giá", ["#E0F7FF", "#7DD3FC", "#3B82F6"]),
    ("void", "Hư không", ["#F0ABFC", "#A855F7", "#4C1D95"]),
    ("rainbow", "Cầu vồng", ["#FF3B3B", "#FFD60A", "#2EE59D", "#22D3EE", "#A855F7"]),
]
OMBRE_SPEEDS = {"slow": 150, "mid": 90, "fast": 50}      # ms mỗi khung (24 khung một vòng)
OMBRE_FRAMES = 24


_tmap_cache = {}


def ombre_tmap(im, hot):
    """Ảnh xám: 0 ở điểm click, 255 ở phần xa nhất (đuôi). Điểm click ở giữa thì chuyển chéo."""
    key = (im.size, tuple(hot), hash(im.getchannel("A").tobytes()))
    if key not in _tmap_cache:
        if len(_tmap_cache) > 64:
            _tmap_cache.clear()
        _tmap_cache[key] = _ombre_tmap(im, hot)
    return _tmap_cache[key]


def _ombre_tmap(im, hot):
    w, h = im.size
    bb = im.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox() or (0, 0, w, h)
    hx, hy = hot
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    if math.hypot(cx - hx, cy - hy) < 0.18 * max(bb[2] - bb[0], bb[3] - bb[1], 1):
        hx, hy = bb[0], bb[1]                         # con trỏ tâm (tâm ngắm, vòng tròn): góc trên trái -> dưới phải
    dx, dy = cx - hx, cy - hy
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    m = max((x - hx) * dx + (y - hy) * dy for x in (bb[0], bb[2]) for y in (bb[1], bb[3])) or 1.0
    k = 255.0 / m
    data = [max(0, min(255, int(((x + 0.5 - hx) * dx + (y + 0.5 - hy) * dy) * k)))
            for y in range(h) for x in range(w)]
    t = Image.new("L", (w, h))
    t.putdata(data)
    return t


_ombre_luts = {}


def ombre_lut(colors, phase=0.0, anim=False):
    """Bảng 256 màu cho từng kênh R, G, B. Chuyển động: dải màu đi qua lại, nối liền khi lặp."""
    key = (tuple(colors), round(phase, 4), anim)
    if key in _ombre_luts:
        return _ombre_luts[key]
    stops = [_rgb(c) for c in colors]
    if anim:
        stops = stops + stops[-2::-1]
    n = len(stops) - 1
    out = ([], [], [])
    for i in range(256):
        u = i / 255
        if anim:
            u = (u * 0.5 + phase) % 1.0
        pos = u * n
        j = min(int(pos), n - 1)
        f = pos - j
        for ch in range(3):
            out[ch].append(int(stops[j][ch] + (stops[j + 1][ch] - stops[j][ch]) * f))
    if len(_ombre_luts) > 200:
        _ombre_luts.clear()
    _ombre_luts[key] = out
    return out


def apply_ombre(im, tmap, lut):
    """Tô dải màu lên phần có màu của ảnh, giữ phần trắng/đen và độ sáng tối (bóng, điểm sáng)."""
    g = Image.merge("RGB", [tmap.point(ch) for ch in lut])
    gh, gs, gv = g.convert("HSV").split()
    rgb = im.convert("RGB")
    _h, sat, val = rgb.convert("HSV").split()
    mask = sat.point(lambda x: max(0, min(255, (x - 40) * 4)))
    ns = ImageChops.multiply(sat.point(lambda x: min(255, int(x * 1.3))), gs)
    nv = ImageChops.multiply(val.point(lambda x: min(255, 60 + x)), gv)
    colored = Image.merge("HSV", (gh, ns, nv)).convert("RGB")
    out = Image.composite(colored, rgb, mask)
    out.putalpha(im.getchannel("A"))
    return out


def ombre_dot(colors, selected, size=30):
    """Ô tròn dải màu (có vòng trắng khi đang chọn); colors=None: ô "+" tự chọn."""
    k = 4
    W = size * k
    out = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    if colors is None:
        d.ellipse([k, k, W - k - 1, W - k - 1], outline="#4A5266", width=k)
        m, t = W // 2, W // 7
        d.line([(m - t, m), (m + t, m)], fill="#9AA3B8", width=int(1.6 * k))
        d.line([(m, m - t), (m, m + t)], fill="#9AA3B8", width=int(1.6 * k))
        return out.resize((size, size), Image.LANCZOS)
    inset = 5 * k if selected else 2 * k
    sw = ombre_swatch(colors, (W - 2 * inset) // k).resize((W - 2 * inset, W - 2 * inset), Image.LANCZOS)
    out.alpha_composite(sw, (inset, inset))
    if selected:
        d.ellipse([k, k, W - k - 1, W - k - 1], outline="#FFFFFF", width=int(1.8 * k))
    return out.resize((size, size), Image.LANCZOS)


def ombre_swatch(colors, size=32, round_=True):
    """Ô tròn (hoặc thanh) dải màu để hiện trên nút."""
    w, h = (size, size) if round_ else (size * 4, size)
    bar = Image.new("RGB", (256, 1))
    lut = ombre_lut(colors)
    bar.putdata([(lut[0][i], lut[1][i], lut[2][i]) for i in range(256)])
    bar = bar.resize((w * 4, h * 4), Image.BILINEAR)
    if round_:
        bar = bar.rotate(-45, resample=Image.BICUBIC, expand=False, fillcolor=_rgb(colors[-1]))
    mask = Image.new("L", (w * 4, h * 4), 0)
    d = ImageDraw.Draw(mask)
    if round_:
        d.ellipse([2, 2, w * 4 - 3, h * 4 - 3], fill=255)
    else:
        d.rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=h * 2, fill=255)
    out = bar.convert("RGBA")
    out.putalpha(mask)
    return out.resize((w, h), Image.LANCZOS)


# ---------------------------------------------------------------- Trình tạo con trỏ (2.2.0)
MAKER_SHAPES = [   # (mã, tên, loại: "poly" có mũi / "center" điểm click ở giữa)
    ("arrow", "Nhọn", "poly"), ("arrow_round", "Bo tròn", "poly"),
    ("arrow_slim", "Mảnh", "poly"), ("shard", "Pha lê", "poly"), ("drop", "Giọt nước", "poly"),
    ("triangle", "Tam giác", "poly"), ("diamond", "Kim cương", "center"), ("dot", "Chấm", "center"),
    ("ring", "Vòng", "center"), ("cross", "Tâm ngắm", "center"),
]
MAKER_SHAPE_DEFAULTS = {   # thông số hợp lý khi đổi sang hình đó
    "arrow": {"width": 1.0, "tail": 1.0, "round": 0.0}, "arrow_round": {"width": 1.0, "tail": 1.0, "round": 0.6},
    "arrow_slim": {"width": 0.9, "tail": 1.0, "round": 0.0}, "shard": {"width": 1.0, "tail": 0.6, "round": 0.0},
    "drop": {"width": 1.0, "tail": 0.6, "round": 0.0}, "triangle": {"width": 1.0, "tail": 0.5, "round": 0.2},
    "diamond": {"width": 0.8, "round": 0.0}, "dot": {"width": 0.5}, "ring": {"width": 0.9, "thick": 0.25},
    "cross": {"width": 1.0, "tail": 0.35, "thick": 0.35},
}
MAKER_DEFAULT = {"shape": "arrow", "width": 1.0, "tail": 1.0, "round": 0.0, "rot": 0, "thick": 0.5,
                 "fill": "solid", "color": "#FF2E93", "ombre": ["#FF2E93", "#FF8A3D", "#FFD60A"],
                 "in_col": "#FFFFFF", "in_w": 7, "out_col": "#0B0D12", "out_w": 4,
                 "tip": True, "shine": True, "shadow": True, "hot": None}


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _maker_poly(sp):
    """Đa giác (đơn vị, mũi ở gốc tọa độ) của các hình có mũi."""
    w, t = sp["width"], sp["tail"]
    sh = sp["shape"]
    if sh in ("arrow", "arrow_round", "arrow_slim"):
        if sh == "arrow_slim":
            base = [(0, 0), (0.04, 0.92), (0.22, 0.70), (0.34, 1.02), (0.43, 0.98), (0.31, 0.66), (0.58, 0.66)]
        else:
            base = [(0, 0), (0, 0.86), (0.22, 0.66), (0.36, 0.98), (0.49, 0.93), (0.35, 0.62), (0.63, 0.62)]
        notch_l, notch_r = base[2], base[5]
        out = []
        for i, (x, y) in enumerate(base):
            if i in (3, 4):                      # đuôi: co giãn theo "Độ dài đuôi"
                nx, ny = (notch_l if i == 3 else notch_r)
                x, y = nx + (x - nx) * t, ny + (y - ny) * t
            out.append((x * w, y))
        return out, -15
    if sh == "shard":   # cánh diều đối xứng theo trục, xoay -45° để mũi ở góc trên trái
        return [(0, 0), (0.24 * w, 0.62), (0, 0.72 + 0.28 * t), (-0.24 * w, 0.62)], -45
    if sh == "drop":
        r = 0.30 * w
        cy = 0.55 + 0.25 * t
        pts = [(0, 0)] + [(r * math.cos(a / 32 * math.pi), cy + r * math.sin(a / 32 * math.pi)) for a in range(64)]
        h = _hull(pts)
        i = h.index((0, 0))
        return h[i:] + h[:i], -45
    if sh == "triangle":
        return [(0, 0), (0.42 * w, 0.62 + 0.3 * t), (-0.42 * w, 0.62 + 0.3 * t)], -45
    return [(0, 0)], 0


def _rot(pts, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(x * ca - y * sa, x * sa + y * ca) for x, y in pts]


def maker_render(sp, size=256):
    """Vẽ con trỏ theo thông số -> (ảnh RGBA size×size, điểm click)."""
    sp = dict(MAKER_DEFAULT, **sp)
    k = size / 256
    pad = (sp["in_w"] + sp["out_w"]) * k + (10 if sp["shadow"] else 4) * k + 4 * k
    SS = 4
    W = size * SS
    mask_hi = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(mask_hi)
    kind = dict((a, c) for a, _, c in MAKER_SHAPES).get(sp["shape"], "poly")
    if kind == "poly":
        pts, base_rot = _maker_poly(sp)
        pts = _rot(pts, base_rot + sp["rot"])          # điểm đầu tiên luôn là mũi
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
        sc = (size - 2 * pad) / span
        ox, oy = pad - min(xs) * sc, pad - min(ys) * sc
        # căn giữa phần dư theo chiều ngắn
        ox += ((size - 2 * pad) - (max(xs) - min(xs)) * sc) / 2 * 0.0
        poly = [((x * sc + ox) * SS, (y * sc + oy) * SS) for x, y in pts]
        d.polygon(poly, fill=255)
        hot = (pts[0][0] * sc + ox, pts[0][1] * sc + oy)
    else:
        c = W / 2
        R = (size / 2 - pad) * SS * min(1.0, 0.55 + 0.45 * sp["width"])
        th = max(2 * SS * k, R * (0.08 + 0.30 * sp["thick"]))
        if sp["shape"] == "dot":
            d.ellipse([c - R * 0.7, c - R * 0.7, c + R * 0.7, c + R * 0.7], fill=255)
        elif sp["shape"] == "ring":
            d.ellipse([c - R, c - R, c + R, c + R], fill=255)
            d.ellipse([c - R + th, c - R + th, c + R - th, c + R - th], fill=0)
        elif sp["shape"] == "diamond":
            rx = R * (0.55 + 0.45 * sp["width"]) / 1.0
            pts = _rot([(0, -R), (rx * 0.8, 0), (0, R), (-rx * 0.8, 0)], sp["rot"])
            d.polygon([(c + x, c + y) for x, y in pts], fill=255)
        else:   # tâm ngắm: 4 thanh có khe hở
            gap = R * (0.15 + 0.35 * sp["tail"])
            h = th / 2
            for ang in (0, 90, 180, 270):
                bar = _rot([(gap, -h), (R, -h), (R, h), (gap, h)], ang + sp["rot"])
                d.polygon([(c + x, c + y) for x, y in bar], fill=255)
        hot = (size / 2, size / 2)
    mask = mask_hi.resize((size, size), Image.LANCZOS)
    if sp["round"] > 0:                                  # bo góc: làm mờ rồi cắt ngưỡng
        r = 1 + sp["round"] * 10 * k
        mask = mask.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 0 if v < 118 else (255 if v > 138 else (v - 118) * 255 // 20))

    def grow(m, w):
        w = int(round(w * k))
        if w <= 0:
            return m
        g = m.filter(ImageFilter.MaxFilter(2 * w + 1))
        return g.filter(ImageFilter.GaussianBlur(0.6))

    m_in = grow(mask, sp["in_w"])
    m_out = grow(m_in, sp["out_w"])
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if sp["shadow"]:
        sh = m_out.filter(ImageFilter.GaussianBlur(5 * k))
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        layer.putalpha(sh.point(lambda v: v * 110 // 255))
        out.alpha_composite(layer, (int(3 * k), int(5 * k)))
    for m, col in ((m_out, sp["out_col"]), (m_in, sp["in_col"])):
        layer = Image.new("RGBA", (size, size), _rgb(col) + (0,))
        layer.putalpha(m)
        out.alpha_composite(layer)
    # thân
    if sp["fill"] == "ombre":
        tm = ombre_tmap(Image.merge("RGBA", (mask, mask, mask, mask)), hot)
        lut = ombre_lut(sp["ombre"])
        body = Image.merge("RGB", [tm.point(ch) for ch in lut]).convert("RGBA")
        body.putalpha(mask)
    else:
        body = Image.new("RGBA", (size, size), _rgb(sp["color"]) + (0,))
        if sp["fill"] == "glass":
            body.putalpha(mask.point(lambda v: v * 150 // 255))
        else:
            body.putalpha(mask)
    if sp["fill"] == "glass":   # lõi trong suốt: xóa phần viền trong phía sau để thấy nền
        inner = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out = Image.composite(inner, out, mask)
    out.alpha_composite(body)
    if sp["shine"]:            # vệt sáng dọc cạnh trên trái
        sh_off = ImageChops.offset(mask, int(6 * k), int(6 * k))
        shine = ImageChops.subtract(mask, sh_off).filter(ImageFilter.GaussianBlur(1.2 * k))
        shine = ImageChops.multiply(shine, mask.filter(ImageFilter.MinFilter(3)))
        layer = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        layer.putalpha(shine.point(lambda v: v * 150 // 255))
        out.alpha_composite(layer)
    if sp["tip"]:
        hx, hy = hot
        r = 7 * k
        tip_col = sp["ombre"][0] if sp["fill"] == "ombre" else sp["color"]
        layer = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
        dd = ImageDraw.Draw(layer)
        dd.ellipse([(hx - r - 2.5 * k) * SS, (hy - r - 2.5 * k) * SS, (hx + r + 2.5 * k) * SS, (hy + r + 2.5 * k) * SS],
                   fill="#FFFFFF")
        dd.ellipse([(hx - r) * SS, (hy - r) * SS, (hx + r) * SS, (hy + r) * SS], fill=mix(tip_col, "#FFFFFF", 0.25))
        out.alpha_composite(layer.resize((size, size), Image.LANCZOS))
    if sp.get("hot"):
        hot = tuple(sp["hot"])
    return out, (int(round(hot[0])), int(round(hot[1])))


def png_to_cur(im, hot):
    """File .cur một ảnh, dữ liệu ảnh là PNG (Windows Vista trở lên đọc được)."""
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    w, h = im.size
    return struct.pack("<HHH", 0, 2, 1) + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hot[0], hot[1],
                                                       len(png), 22) + png


# ---------------------------------------------------------------- Phím tắt tùy chỉnh
HOTKEY_MODS = [("ctrl", VK_CONTROL, "Ctrl"), ("alt", VK_MENU, "Alt"), ("shift", VK_SHIFT, "Shift")]
HOTKEY_ACTIONS = ["toggle", "shape", "color", "quit", "find"]
_VK_NAMES = {0x20: "Space", 0x21: "PgUp", 0x22: "PgDn", 0x23: "End", 0x24: "Home", 0x2D: "Ins", 0x2E: "Del",
             0x13: "Pause", 0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
             0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'"}


def vk_name(vk):
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    if 0x60 <= vk <= 0x69:
        return f"Num{vk - 0x60}"
    return _VK_NAMES.get(vk, "")


HOTKEY_VKS = [v for v in list(range(0x30, 0x3A)) + list(range(0x41, 0x5B)) + list(range(0x60, 0x6A))
              + list(range(0x70, 0x88)) + list(_VK_NAMES)]


def clean_hotkeys(hk):
    """Kiểm tra phím tắt đọc từ file cài đặt; mục nào hỏng thì dùng mặc định."""
    out = json.loads(json.dumps(DEFAULT_CFG["hotkeys"]))
    if not isinstance(hk, dict):
        return out
    names = {m for m, _, _ in HOTKEY_MODS}
    for act in HOTKEY_ACTIONS:
        b = hk.get(act)
        if not isinstance(b, dict):
            continue
        mods = [m for m in b.get("mods", []) if m in names] if isinstance(b.get("mods"), list) else []
        if not ({"ctrl", "alt"} & set(mods)):
            continue
        if act == "color":
            out[act] = {"mods": mods}
        elif isinstance(b.get("vk"), int) and b["vk"] in HOTKEY_VKS:
            out[act] = {"mods": mods, "vk": b["vk"]}
    return out


def hotkey_parts(binding, act):
    """Các phím để hiển thị, vd ['Ctrl', 'Alt', 'H']."""
    parts = [label for m, _, label in HOTKEY_MODS if m in binding["mods"]]
    return parts + (["1–5"] if act == "color" else [vk_name(binding["vk"])])


def mods_down():
    return {m for m, vk, _ in HOTKEY_MODS if key_down(vk)}


# ---------------------------------------------------------------- File con trỏ Windows (.cur / .ani)
def _ico_entries(data):
    reserved, typ, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or typ not in (1, 2) or not 0 < count < 256:
        raise ValueError("Không phải file .cur/.ico hợp lệ")
    out = []
    for i in range(count):
        w, h, _c, _r, hx, hy, size, off = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        out.append((w or 256, h or 256, hx, hy, size, off, typ))
    return out


def decode_cur(data):
    """Ảnh lớn nhất trong file .cur/.ico và điểm click (None nếu là .ico)."""
    w, h, hx, hy, size, off, typ = max(_ico_entries(data), key=lambda e: e[0] * e[1])
    blob = data[off:off + size]
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        im = Image.open(io.BytesIO(blob)).convert("RGBA")
    else:   # ảnh DIB: gói lại thành file .ico một ảnh để Pillow đọc được
        head = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, size, 22)
        im = Image.open(io.BytesIO(head + blob)).convert("RGBA")
    if typ != 2:
        return im, None
    return im, (round(hx * im.width / w), round(hy * im.height / h))


def decode_ani(data):
    """Con trỏ động .ani: (danh sách ảnh, điểm click, [(chỉ số ảnh, thời gian ms), ...])."""
    if data[:4] != b"RIFF" or data[8:12] != b"ACON":
        raise ValueError("Không phải file .ani hợp lệ")

    def chunks(start, end):
        while start + 8 <= end:
            cid = data[start:start + 4]
            ln = struct.unpack_from("<I", data, start + 4)[0]
            yield cid, start + 8, ln
            start += 8 + ln + (ln & 1)

    frames, rate, seq, jif = [], None, None, 6
    for cid, pos, ln in chunks(12, len(data)):
        if cid == b"anih" and ln >= 36:
            jif = struct.unpack_from("<9I", data, pos)[7] or 6
        elif cid == b"rate":
            rate = list(struct.unpack_from(f"<{ln // 4}I", data, pos))
        elif cid == b"seq ":
            seq = list(struct.unpack_from(f"<{ln // 4}I", data, pos))
        elif cid == b"LIST" and data[pos:pos + 4] == b"fram":
            for c2, p2, l2 in chunks(pos + 4, pos + ln):
                if c2 == b"icon":
                    frames.append(decode_cur(data[p2:p2 + l2]))
    if not frames:
        raise ValueError("File .ani không có ảnh nào")
    order = [i for i in (seq or range(len(frames))) if i < len(frames)] or [0]
    steps = [(fi, max(16, round((rate[i] if rate and i < len(rate) else jif) * 1000 / 60)))
             for i, fi in enumerate(order)]
    return [f[0] for f in frames], frames[0][1], steps


def load_cursor_file(path):
    """Đọc ảnh hoặc file con trỏ: (danh sách ảnh RGBA, điểm click trong ảnh hoặc None, bước hoạt ảnh hoặc None)."""
    ext = Path(path).suffix.lower()
    data = Path(path).read_bytes()
    if ext == ".ani":
        return decode_ani(data)
    if ext == ".cur":
        im, hot = decode_cur(data)
        return [im], hot, None
    im = Image.open(io.BytesIO(data))
    if getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1:
        frames, steps = [], []
        for i, fr in enumerate(ImageSequence.Iterator(im)):
            frames.append(fr.convert("RGBA"))
            steps.append((i, max(20, int(fr.info.get("duration", 100) or 100))))
            if i >= 119:           # tối đa 120 khung hình
                break
        return frames, None, steps
    return [im.convert("RGBA")], None, None


# ---------------------------------------------------------------- Màn hình & Fullscreen
user32.MonitorFromPoint.restype = wintypes.HANDLE
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]


def monitor_scale(x, y):
    """Tỉ lệ phóng (DPI / 96) của màn hình chứa điểm (x, y)."""
    try:
        mon = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)       # MONITOR_DEFAULTTONEAREST
        dx, dy = wintypes.UINT(), wintypes.UINT()
        if ctypes.windll.shcore.GetDpiForMonitor(mon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0 and dx.value:
            return max(1.0, min(4.0, dx.value / 96))
    except Exception:
        pass
    return 1.0


def fullscreen_exclusive():
    """True khi có ứng dụng Direct3D đang chạy ở chế độ Fullscreen độc quyền."""
    st = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(st)) == 0:
            return st.value == 3             # QUNS_RUNNING_D3D_FULL_SCREEN
    except Exception:
        pass
    return False


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


def star_icon(filled, color, size=16):
    def draw(d, s):
        k = s * size / 16
        pts = []
        for i in range(10):
            r = (7.2 if i % 2 == 0 else 3.1) * k
            a = math.pi / 2 + i * math.pi / 5
            pts.append((8 * k + r * math.cos(a), 8.6 * k - r * math.sin(a)))
        if filled:
            d.polygon(pts, fill=color)
        else:
            d.line(pts + [pts[0]], fill=color, width=max(1, int(1.4 * k)), joint="curve")
    return _ss(draw, size)


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
        if kind == "trash":
            w = max(1, int(1.6 * s))
            d.line([(3 * s, 4.5 * s), (13 * s, 4.5 * s)], fill=color, width=w)
            d.line([(6.5 * s, 4.5 * s), (6.5 * s, 2.5 * s), (9.5 * s, 2.5 * s), (9.5 * s, 4.5 * s)], fill=color, width=w)
            d.polygon([(4.5 * s, 6 * s), (11.5 * s, 6 * s), (10.8 * s, 14 * s), (5.2 * s, 14 * s)], outline=color, width=w)
            return
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


def render_shape(shape, color, size, img_rgba, hotspot, file_hot=None):
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
        top_left = hotspot == "Góc trên trái" or (hotspot == "Theo file" and file_hot)
        pos = (0, 0) if top_left else ((n - pic.width) // 2, (n - pic.height) // 2)
        im.alpha_composite(pic, pos)
    im = im.resize((size, size), Image.LANCZOS)
    if shape == "Mũi tên":
        hot = (round(3 * size / 64), round(3 * size / 64))
    elif shape == "Ảnh tải lên" and hotspot == "Theo file" and file_hot:
        k2 = size / max(img_rgba.size)
        hot = (min(size - 1, round(file_hot[0] * k2)), min(size - 1, round(file_hot[1] * k2)))
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
    ("EzPink", "Mảnh hồng", "ezpink.png", (25, 21), "#FF2E93"),
    # Bộ EzCursor phong cách game (1.8.0)
    ("ez_crosshair", "Tâm ngắm Neon", "ez/ez_crosshair.png", (128, 128), "#3B7BF9"),
    ("ez_sword", "Mũi kiếm", "ez/ez_sword.png", (26, 26), "#3B7BF9"),
    ("ez_crystal", "Mũi tên Pha lê", "ez/ez_crystal.png", (24, 24), "#3B7BF9"),
    ("ez_gem", "Viên ngọc", "ez/ez_gem.png", (26, 26), "#3B7BF9"),
    ("ez_rune", "Ký tự Rune", "ez/ez_rune.png", (128, 128), "#3B7BF9"),
    ("ez_orb", "Cầu năng lượng", "ez/ez_orb.png", (128, 128), "#3B7BF9"),
    ("ez_flame", "Ngọn lửa", "ez/ez_flame.png", (24, 24), "#3B7BF9"),
    ("ez_spear", "Mũi giáo", "ez/ez_spear.png", (24, 24), "#3B7BF9"),
    ("ez_feather", "Lông vũ", "ez/ez_feather.png", (24, 24), "#3B7BF9"),
    ("ez_star", "Ngôi sao", "ez/ez_star.png", (128, 128), "#3B7BF9"),
    ("ez_shot", "Mũi tên Bắn", "ez/ez_shot.png", (24, 24), "#3B7BF9"),
    ("ez_neon", "Mũi tên Neon", "ez/ez_neon.png", (24, 24), "#3B7BF9"),
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


_own_tinted = {}


def own_image_colored(shape, color):
    """Con trỏ EzCursor đổi sang màu đã chọn (giữ phần trắng/đen), có cache."""
    key = (shape, color.lower())
    if key not in _own_tinted:
        base = own_image(shape)
        if base is None:
            return None
        if len(_own_tinted) > 40:
            _own_tinted.clear()
        _own_tinted[key] = tint_image(base, color)
    return _own_tinted[key]


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

    MOVE_FLAGS = 0x1 | 0x4 | 0x10 | 0x200 | 0x400      # NOSIZE | NOZORDER | NOACTIVATE | NOOWNERZORDER | NOSENDCHANGING

    def move(self, x, y):
        user32.SetWindowPos(self.hwnd, None, x, y, 0, 0, self.MOVE_FLAGS)

    def raise_top(self):
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # NOSIZE | NOMOVE | NOACTIVATE

    def show(self, on):
        if on != self.visible:
            user32.ShowWindow(self.hwnd, 4 if on else 0)    # SW_SHOWNOACTIVATE / SW_HIDE
            self.visible = on
            if on:
                self.raise_top()

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


TASKBAR_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def shell_ui_open(keep_taskbar=False):
    """True khi giao diện riêng của Windows (Start, Search, taskbar, xem trước...) đang mở hoặc ở dưới chuột.
    keep_taskbar: rê chuột trên thanh taskbar vẫn giữ con trỏ EzCursor."""
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
        cls = class_name(root)
        if cls not in SHELL_HOVER_OK and not (keep_taskbar and cls in TASKBAR_CLASSES):
            exe = exe_name(pid_of(root)).lower()
            if exe in SHELL_UI_EXES or exe == "explorer.exe":
                return True
    return False


def outline_width(size):
    return max(2, round(size / 20))


def pad_image(im, hot, p):
    out = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0))
    out.alpha_composite(im, (p, p))
    return out, (hot[0] + p, hot[1] + p)


def add_outline(im, hot, color, w):
    """Viền màu bám theo hình con trỏ (vẽ bên ngoài, không che con trỏ)."""
    p = w + 2
    a = Image.new("L", (im.width + 2 * p, im.height + 2 * p), 0)
    a.paste(im.getchannel("A").point(lambda v: 255 if v > 90 else 0), (p, p))
    ring = a.filter(ImageFilter.MaxFilter(2 * w + 1)).filter(ImageFilter.GaussianBlur(0.7))
    out = Image.new("RGBA", a.size, color)
    out.putalpha(ring)
    out.alpha_composite(im, (p, p))
    return out, (hot[0] + p, hot[1] + p)


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
        self.cfg = ProfileCfg(load_cfg())
        self.mine_sig = 0               # tăng mỗi khi danh sách "Con trỏ của bạn" đổi
        self.edit_profile = None        # hồ sơ đang chỉnh trong giao diện (None = Mặc định)
        self.play_profile = None        # hồ sơ của game đang chơi
        self.tray_pr = None             # hồ sơ mà menu khay đang áp vào (game chơi gần nhất / hồ sơ chọn gần nhất)
        self.tray_sig = None
        self.sys_cache = {}            # HCURSOR đã tạo cho từng biến thể (chế độ Con trỏ thật)
        self.mode_on = None
        self.sys_key = "?"
        self.cat_entries = None         # danh sách kho trực tuyến (None = chưa tải)
        self.cat_status = ("idle", 0)
        self.cat_busy = False
        self.cat_dl = set()             # đang tải về
        self.cat_thumbs = {}
        self.img_cache = {}
        self.profile_menus = []
        global LANG
        LANG = self.cfg["language"]
        self.enabled = bool(self.cfg["enabled"])
        self.active = False
        self.src_img = None
        self.src_frames = None      # khung hình của ảnh động (.ani / .gif)
        self.src_steps = None
        self.src_hot = None         # điểm click lấy từ file .cur / .ani
        self.cur_scale = 1.0
        self.fs_block = False       # game đang ở Fullscreen độc quyền
        self.fs_checked = 0.0
        self.fs_warned = set()
        self.capturing = False
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
        self.variants = {}          # None / "left" / "right" -> (ảnh, điểm click, màu quầng)
        self.frame_sets = None      # các bộ khung hình động theo trạng thái giữ chuột
        self.hold_state = None
        self.shown_img = None       # ảnh con trỏ đang hiển thị (không tính hiệu ứng tìm con trỏ)
        self.find_t0 = None         # thời điểm bắt đầu hiệu ứng tìm con trỏ
        self.find_hot = None
        self.find_ring_only = False
        self.find_cool = 0.0
        self.sh_last_x = None
        self.sh_dir = 0
        self.sh_seg = 0
        self.sh_rev = []
        self.quitting = False
        self.safe_mode = False
        self.err_times = []
        self.logged_errors = set()
        self.last_move = None
        self.t_active = self.t_keys = self.t_flags = 0.0
        self.want_active = False
        self.cf_next = 0.0
        self.cursor_durations = None
        self.pv_idx = 0
        self.pv_next = 0.0
        self._cf_job = None
        self.shell_open = False

        self.F = Fonts(self.ov)
        self.ov.report_callback_exception = self.on_tk_error

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

        self.icon = pystray.Icon(APP_NAME, make_tray_icon(), APP_NAME, self.build_tray_menu())
        self.icon.run_detached()

        self.refresh_apps()
        self.refresh()
        self.tick()
        self.anim()
        self.fx_loop()
        self.follow_loop()
        self.ov.after(5000, self.auto_check_update)
        if not self.cfg["setup_done"] or "--setup" in sys.argv:
            self.ov.after(700, self.wait_setup)

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

    def page_top(self, page, title, sub, pady):
        """Tiêu đề tab kèm ô chọn hồ sơ đang chỉnh."""
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x", pady=pady)
        self.header(top, title, sub).pack(side="left", anchor="w")
        box = ctk.CTkFrame(top, fg_color="transparent")
        box.pack(side="right", anchor="s")
        ctk.CTkLabel(box, text=T("Đang chỉnh"), font=self.F.b(11), text_color=MUTED, height=14).pack(anchor="w")
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(anchor="w")
        menu = ctk.CTkOptionMenu(row, values=[""], command=self.pick_profile, width=210, height=32,
                                 corner_radius=8, fg_color=FIELD, button_color=mix(CARD, ACCENT, 0.35),
                                 button_hover_color=mix(CARD, ACCENT, 0.5), text_color=TEXT,
                                 dropdown_fg_color=CARD, dropdown_hover_color=mix(CARD, ACCENT, 0.2),
                                 dropdown_text_color=TEXT, font=self.F.b(12, strong=True),
                                 dropdown_font=self.F.b(12), dynamic_resizing=False)
        menu.pack(side="left")
        rm = ctk.CTkButton(row, text="", width=32, height=32, corner_radius=8, fg_color="transparent",
                           hover_color=mix(CARD, "#FF5A5A", 0.22), border_width=1, border_color=BORDER,
                           image=ctk.CTkImage(simple_icon("trash", "#FF8A8A", 32), size=(14, 14)),
                           command=self.delete_profile)
        self.profile_menus.append((menu, rm))
        return top

    # ------------------------------------------------------------ Menu khay hệ thống
    def build_tray_menu(self):
        """Menu chuột phải ở icon khay. Các mục được dựng lại mỗi lần gọi icon.update_menu()."""
        M, I = pystray.Menu, pystray.MenuItem
        put = self.q.put

        def act(cmd):                 # pystray chỉ nhận hàm có tối đa 2 tham số
            return lambda i, it: put(cmd)

        def shape_item(label, shape):
            return I(label, act(("tray_shape", shape)),
                     checked=lambda it: self.cfg["shape"] == shape, radio=True)

        def mine_item(f, cur):
            return I(f.stem, act(("tray_mine", str(f))),
                     checked=lambda it: cur is not None and Path(cur) == f, radio=True)

        def profile_item(pr):
            return I(self.profile_label(pr), act(("tray_profile", None if pr is None else pr["name"])),
                     checked=lambda it: self.tray_pr is pr, radio=True)

        def own_items():
            return [shape_item(T(c[1]), c[0]) for c in OWN_CURSORS]

        def basic_items():
            return [shape_item(T(x), x) for x in ("Mũi tên", "Vòng tròn", "Dấu thập", "Chấm tròn", "Kim cương")]

        def mine_items():
            files = my_cursor_files()
            if not files:
                return [I(T("(chưa có)"), None, enabled=False)]
            cur = self.cfg["image"] if self.cfg["shape"] == "Ảnh tải lên" else None
            return [mine_item(f, cur) for f in reversed(files[-20:])]

        def fav_item(fid, cur):
            return I(self.fav_label(fid), act(("tray_fav", fid)), checked=lambda it: fid == cur, radio=True)

        def cursor_items():
            yield I(lambda it: T("Áp cho: {n}").format(n=self.profile_label(self.tray_pr)), None,
                    enabled=False, visible=bool(self.cfg["profiles"]))
            favs = [f for f in self.cfg["favorites"] if self.fav_valid(f)]
            if favs:
                cur = self.current_fav_id()
                yield I("★ " + T("Yêu thích"), M(*[fav_item(f, cur) for f in favs]))
            yield I(T("Bộ EzCursor"), M(*own_items()))
            yield I(T("Hình cơ bản"), M(*basic_items()))
            yield shape_item("Bibata", "Bibata")
            yield I(T("Con trỏ của bạn"), M(*mine_items()))

        def profile_items():
            for pr in [None] + list(self.cfg["profiles"]):
                yield profile_item(pr)

        def items():
            yield I(T("Mở EzCursor"), lambda i, it: put("show"), default=True)
            yield I(T("Bật con trỏ"), lambda i, it: put("toggle"), checked=lambda it: self.enabled)
            yield M.SEPARATOR
            yield I(T("Đổi con trỏ"), M(*cursor_items()))
            if self.cfg["profiles"]:
                yield I(T("Hồ sơ"), M(*profile_items()))
            yield M.SEPARATOR
            yield I(T("Kiểm tra cập nhật"), lambda i, it: put("check_update"))
            yield I(T("Thoát"), lambda i, it: put("quit"))

        return M(lambda: list(items()))

    def tray_state(self):
        c = self.cfg
        return (LANG, self.enabled, c["shape"], c["image"], c["bibata_cursor"], tuple(c["favorites"]), id(self.tray_pr),
                tuple(pr["name"] for pr in c["profiles"]), self.mine_sig)

    def sync_tray(self, force=False):
        """Cập nhật menu khay khi có gì thay đổi (đổi con trỏ bằng phím tắt, giao diện...)."""
        sig = self.tray_state()
        if sig == self.tray_sig and not force:
            return
        self.tray_sig = sig
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def tray_use_profile(self):
        """Chuyển giao diện sang hồ sơ mà menu khay đang áp vào."""
        pr = self.tray_pr
        if pr is not None and pr not in self.cfg["profiles"]:
            pr = self.tray_pr = None
        if self.edit_profile is not pr:
            self.edit_profile = pr
            self.update_profile_menus()
        if not self.active:
            self.use_style(self.style_of(pr))

    def handle_tray(self, cmd, arg):
        if cmd == "tray_profile":
            self.tray_pr = next((p for p in self.cfg["profiles"] if p["name"] == arg), None)
            self.tray_use_profile()
        elif cmd == "tray_shape":
            self.tray_use_profile()
            self.set_shape(arg)
        elif cmd == "tray_fav":
            self.tray_use_profile()
            self.use_fav(arg)
        elif cmd == "tray_mine":
            self.tray_use_profile()
            if Path(arg).is_file():
                self.use_my_cursor(arg)
        self.save()
        self.sync_tray()

    # ------------------------------------------------------------ Hồ sơ riêng từng game
    def profile_label(self, pr):
        return T("Mặc định (mọi game)") if pr is None else pr["name"]

    def update_profile_menus(self):
        values = [self.profile_label(None)] + [pr["name"] for pr in self.cfg["profiles"]]
        cur = self.profile_label(self.edit_profile)
        for menu, rm in self.profile_menus:
            try:
                menu.configure(values=values)
                menu.set(cur)
                if self.edit_profile is None:
                    rm.pack_forget()
                elif not rm.winfo_ismapped():
                    rm.pack(side="left", padx=(6, 0))
            except tk.TclError:
                pass

    def profile_for_exe(self, exe):
        exe = (exe or "").lower()
        for pr in self.cfg["profiles"]:
            if exe in (e.lower() for e in pr["exes"]):
                return pr
        return None

    def style_of(self, pr):
        return self.cfg.base if pr is None else pr["style"]

    def pick_profile(self, label):
        pr = next((p for p in self.cfg["profiles"] if p["name"] == label), None)
        self.edit_profile = pr
        self.tray_pr = pr
        self.update_profile_menus()
        if not self.active:
            self.use_style(self.style_of(pr))

    def use_style(self, style, force=False):
        """Chuyển cài đặt kiểu con trỏ sang bộ khác và vẽ lại."""
        if style is self.cfg.target and not force:
            return
        self.cfg.target = style
        self.load_image(self.cfg["image"], silent=True) if self.cfg["image"] else self.clear_image()
        try:
            hidden = not self.win.winfo_viewable()
        except tk.TclError:
            hidden = False
        if hidden:          # cửa sổ đang ẩn (đang chơi game): chỉ đổi con trỏ, giao diện cập nhật khi mở lại
            self.rebuild_overlay()
            self.update_status()
            self.ui_dirty = True
            return
        self.sync_style_widgets()
        self.refresh()

    def sync_style_widgets(self):
        """Cập nhật các ô điều khiển giữ trạng thái riêng theo bộ kiểu đang chọn."""
        c = self.cfg
        try:
            self.size_slider.set(c["size"])
            self.tint_var.set(c["tint_image"])
            self.glow_var.set(c["glow"])
            self.hot_seg.set(T(c["hotspot"]))
            self.img_label.configure(text=Path(c["image"]).name if c["image"] and self.src_img is not None
                                     else T("(chưa có ảnh)"))
            if getattr(self, "style_seg", None):
                self.style_seg.set({v: k for k, v in self.style_map.items()}.get(c["bibata_style"]))
                self.hand_seg.set({v: k for k, v in self.hand_map.items()}.get(c["bibata_hand"]))
            self.fx_color_seg.set({v: k for k, v in self.fx_color_map.items()}.get(c["fx_color"]))
            self.fx_dens_seg.set({v: k for k, v in self.fx_dens_map.items()}.get(c["fx_density"]))
            for side in ("left", "right"):
                self.hold_vars[side].set(c[f"hold_{side}"])
                col = c[f"hold_{side}_color"]
                self.hold_btns[side].configure(fg_color=col, hover_color=col)
        except (tk.TclError, AttributeError):
            pass

    def create_profile(self, title, exes):
        """Tạo hồ sơ riêng (sao chép kiểu Mặc định) cho game, rồi mở tab Con trỏ để chỉnh."""
        names = {pr["name"] for pr in self.cfg["profiles"]}
        name, i = title, 2
        while name in names or name == self.profile_label(None):
            name, i = f"{title} {i}", i + 1
        st = {k: self.cfg.base[k] for k in STYLE_KEYS}
        st = json.loads(json.dumps(st))
        pr = {"name": name, "exes": list(exes), "style": st}
        self.cfg["profiles"].append(pr)
        self.tray_pr = pr
        added = [e for e in exes if e.lower() not in self.app_set]
        if added:                # game có hồ sơ riêng thì chắc chắn được áp dụng
            self.cfg["apps"] = self.cfg["apps"] + added
            self.update_app_set()
            self.update_applied_label()
        self.edit_profile = pr
        self.update_profile_menus()
        self.use_style(pr["style"])
        self.show_tab("cursor")
        self.save()

    def open_profile(self, exes, title):
        pr = next((self.profile_for_exe(e) for e in exes if self.profile_for_exe(e)), None)
        if pr is None:
            self.create_profile(title, exes)
            return
        self.edit_profile = pr
        self.tray_pr = pr
        self.update_profile_menus()
        self.use_style(pr["style"])
        self.show_tab("cursor")

    def delete_profile(self):
        pr = self.edit_profile
        if pr is None:
            return
        if not messagebox.askyesno(APP_NAME, T("Xóa hồ sơ riêng \"{n}\"? Game này sẽ dùng lại kiểu Mặc định.")
                                   .format(n=pr["name"]), parent=self.win):
            return
        img = pr["style"].get("image")
        if img and Path(img).name.startswith("custom-"):
            try:
                Path(img).unlink()
            except OSError:
                pass
        self.cfg["profiles"].remove(pr)
        self.edit_profile = None
        self.play_profile = None
        if self.tray_pr is pr:
            self.tray_pr = None
        self.update_profile_menus()
        self.use_style(self.cfg.base, force=True)
        if self.tab == "apps":
            self.refresh_apps()

    def pick_target(self):
        """Hồ sơ cần dùng lúc này: của game đang chơi nếu đang hoạt động, nếu không thì hồ sơ đang chỉnh."""
        if self.active:
            self.play_profile = self.profile_for_exe(self.fg_exe)
            return self.style_of(self.play_profile)
        return self.style_of(self.edit_profile)

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
        self.update_profile_menus()
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
        self.toggle_hint = ctk.CTkLabel(st, text=" + ".join(hotkey_parts(self.cfg["hotkeys"]["toggle"], "toggle")),
                                        font=self.F.m(11), text_color=MUTED)
        self.toggle_hint.pack(anchor="w", padx=14, pady=(4, 12))

    def build_cursor_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.page_top(page, "CON TRỎ", "Chọn hình dạng, màu sắc và kích thước con trỏ trong game.", (0, 16))
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
        self.build_ombre_box(pv)

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

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text=T("Phóng theo tỉ lệ màn hình"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.dpi_var = tk.BooleanVar(value=self.cfg["dpi_scale"])
        self.switch(row, self.dpi_var, self.set_dpi_scale).pack(side="right")
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
        self.page_top(page, "BỘ SƯU TẬP", "Con trỏ của EzCursor và bộ Bibata. Bấm vào con trỏ muốn dùng.", (0, 12))
        self.bib_tiles, self.own_tiles = {}, {}
        if getattr(self, "lib_view", None) is None:
            self.lib_view = {"Bibata": "bibata", "Ảnh tải lên": "mine"}.get(self.cfg["shape"], "ez")
        has_bib = BIBATA_DIR.exists()

        seg_kw = dict(height=34, font=self.F.b(12, strong=True), fg_color=FIELD, unselected_color=FIELD,
                      unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                      selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        self.view_map = {T("Bộ EzCursor"): "ez", "Bibata": "bibata", T("Của bạn"): "mine", T("Trực tuyến"): "online"}
        if not has_bib:
            del self.view_map["Bibata"]
        self.view_seg = ctk.CTkSegmentedButton(head, values=list(self.view_map),
                                               command=lambda v: self.set_lib_view(self.view_map[v]),
                                               **dict(seg_kw, height=36, font=self.F.b(13, strong=True)))
        self.view_seg.pack(side="left")
        self.view_seg.set({v: k for k, v in self.view_map.items()}[self.lib_view])

        # Hàng chủ đề: mỗi nhóm một bộ nút
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x")
        self.theme_caps = self.caps(top, "CHỦ ĐỀ")
        self.theme_caps.pack(anchor="w")
        self.chip_rows = {}
        self.theme_buttons, self.own_theme_buttons = {}, {}
        for view in ("ez", "bibata", "mine", "online"):
            row = ctk.CTkFrame(top, fg_color="transparent")
            self.chip_rows[view] = row
        self.cyan_button(self.chip_rows["online"], "Làm mới", lambda: self.start_catalog(force=True),
                         ctk.CTkImage(simple_icon("refresh", CYAN_TEXT, 32), size=(16, 16))).pack(side="left")
        self.cat_label = ctk.CTkLabel(self.chip_rows["online"], text="", font=self.F.b(12), text_color=TEXT2,
                                      wraplength=520, justify="left")
        self.cat_label.pack(side="left", padx=(12, 0))
        self.mine_theme_buttons = {}
        for key, label in (("original", T("Màu gốc")), ("tint", T("Tô màu"))):
            b = ctk.CTkButton(self.chip_rows["mine"], text=label, height=40, width=130, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_mine_tint(k == "tint"))
            b.pack(side="left", padx=(0, 8))
            self.mine_theme_buttons[key] = b
        self.mine_edit = ctk.CTkButton(head, text=T("Sửa con trỏ này"), command=self.edit_made_cursor, height=36,
                                       corner_radius=10, border_width=1, border_color=ACCENT,
                                       fg_color=mix(CARD, ACCENT, 0.10), hover_color=mix(CARD, ACCENT, 0.22),
                                       text_color="#FFFFFF", font=self.F.b(12, strong=True))
        self.mine_del = ctk.CTkButton(head, text=T("Xóa con trỏ này"), command=self.delete_my_cursor, height=36,
                                      corner_radius=10, border_width=1, border_color="#FF5A5A",
                                      fg_color=mix(CARD, "#FF5A5A", 0.10), hover_color=mix(CARD, "#FF5A5A", 0.22),
                                      text_color="#FF8A8A", font=self.F.b(12, strong=True),
                                      image=ctk.CTkImage(simple_icon("trash", "#FF8A8A", 32), size=(14, 14)))
        own_themes = [("original", T("Màu gốc")), ("custom", T("Tùy chỉnh"))]
        for key, label in own_themes:
            b = ctk.CTkButton(self.chip_rows["ez"], text=label, height=40, width=130, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_own_theme(k))
            b.pack(side="left", padx=(0, 8))
            self.own_theme_buttons[key] = b
        self.ombre_chips = []
        for view in ("ez", "bibata", "mine"):
            b = ctk.CTkButton(self.chip_rows[view], text="Ombre", height=40, width=118, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda v=view: self.lib_ombre(v))
            self.ombre_chips.append(b)
        themes = [(k, v[0]) for k, v in BIBATA_THEMES.items()] + [("custom", T("Tùy chỉnh"))]
        for key, label in themes:
            b = ctk.CTkButton(self.chip_rows["bibata"], text=label, height=40, width=118, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_bib("bibata_theme", k))
            b.pack(side="left", padx=(0, 8))
            self.theme_buttons[key] = b
        for b in self.ombre_chips:
            b.pack(side="left", padx=(0, 8))

        self.sw_caps = self.caps(page, "MÀU TÙY CHỈNH")
        self.sw_caps.pack(anchor="w", pady=(12, 0))
        sw = ctk.CTkFrame(page, fg_color="transparent")
        sw.pack(fill="x", pady=(6, 12))
        self.sw_row = sw
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
        # Kiểu Bibata nằm cùng hàng ô màu, chỉ hiện ở nhóm Bibata
        self.bib_opts = ctk.CTkFrame(head, fg_color="transparent")
        self.style_map = {T("Modern · bo tròn"): "modern", T("Original · góc nhọn"): "original"}
        self.hand_map = {T("Thuận tay phải"): "right", T("Thuận tay trái"): "left"}
        small = dict(seg_kw, height=36, font=self.F.b(12, strong=True))
        self.hand_seg = ctk.CTkSegmentedButton(self.bib_opts, values=list(self.hand_map),
                                               command=lambda v: self.set_bib("bibata_hand", self.hand_map[v]), **small)
        self.hand_seg.pack(side="right")
        self.style_seg = ctk.CTkSegmentedButton(self.bib_opts, values=list(self.style_map),
                                                command=lambda v: self.set_bib("bibata_style", self.style_map[v]), **small)
        self.style_seg.pack(side="right", padx=(0, 6))
        self.style_seg.set({v: k for k, v in self.style_map.items()}.get(self.cfg["bibata_style"], T("Modern · bo tròn")))
        self.hand_seg.set({v: k for k, v in self.hand_map.items()}.get(self.cfg["bibata_hand"], T("Thuận tay phải")))

        grid = self.card(page)
        grid.pack(fill="both", expand=True)
        self.lib_card = grid
        cols = 5
        self.lib_grids = {}
        for view in ("ez", "bibata", "mine", "online"):
            if view in ("mine", "online"):
                inner = ctk.CTkScrollableFrame(grid, fg_color="transparent", scrollbar_button_color=BORDER,
                                               scrollbar_button_hover_color="#3A4152")
            else:
                inner = ctk.CTkFrame(grid, fg_color="transparent")
            for i in range(cols):
                inner.grid_columnconfigure(i, weight=1, uniform="t")
            self.lib_grids[view] = inner
        self.mine_tiles = {}
        self.star_btns = {}
        for shape, label, _f, _h, _g in OWN_CURSORS:
            if own_image(shape) is None:
                continue
            n = len(self.own_tiles)
            b = ctk.CTkButton(self.lib_grids["ez"], text=T(label), compound="top", height=94, width=10,
                              corner_radius=12, border_width=1, font=self.F.b(12, strong=True),
                              command=lambda sh=shape: self.pick_own(sh))
            b.grid(row=n // cols, column=n % cols, sticky="ew", padx=4, pady=4)
            self.own_tiles[shape] = b
            self.add_star(b, shape)
        if has_bib:
            for i, (name, label) in enumerate(BIBATA_CURSORS):
                b = ctk.CTkButton(self.lib_grids["bibata"], text=T(label), compound="top", height=94, width=10,
                                  corner_radius=12, border_width=1, font=self.F.b(12),
                                  command=lambda n=name: self.pick_bibata(n))
                b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
                self.bib_tiles[name] = b
                self.add_star(b, "bib:" + name)

        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(foot, text=T("Bấm ☆ để thêm vào Yêu thích. Ctrl+Alt+R sẽ chỉ đổi giữa các con trỏ yêu thích."),
                     font=self.F.b(12), text_color=TEXT2).pack(side="left")
        self.bib_link = ctk.CTkLabel(foot, text="Bibata © Abdulkaiz Khatri · GPL-3.0", font=self.F.b(12),
                                     text_color=CYAN_TEXT, cursor="hand2")
        self.bib_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ful1e5/Bibata_Cursor"))
        self._lib_sig = None
        self._own_sig = None
        self.rebuild_mine_tiles()
        self.cat_tiles = {}
        self.build_online_tiles()
        self.show_lib_view()
        return page

    def rebuild_mine_tiles(self):
        """Dựng lại lưới "Của bạn": ô Thêm + mỗi con trỏ đã lưu."""
        self.mine_sig += 1
        grid = getattr(self, "lib_grids", {}).get("mine")
        if grid is None:
            return
        for w in grid.winfo_children():
            w.destroy()
        self.mine_tiles = {}
        self.star_btns = {k: v for k, v in getattr(self, "star_btns", {}).items() if not k.startswith("my:")}
        cols = 5
        make = ctk.CTkButton(grid, text=T("✦ Tạo con trỏ"), compound="top", height=94, width=10, corner_radius=12,
                             border_width=1, border_color=mix(BORDER, ACCENT, 0.6), fg_color=mix(CARD, ACCENT, 0.08),
                             hover_color=mix(CARD, ACCENT, 0.18), text_color="#FFFFFF", font=self.F.b(12, strong=True),
                             image=ctk.CTkImage(maker_render({"fill": "ombre", "in_w": 9, "out_w": 0, "shadow": False},
                                                             64)[0], size=(32, 32)),
                             command=self.open_maker)
        make.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        add = ctk.CTkButton(grid, text=T("+ Thêm con trỏ"), compound="top", height=94, width=10, corner_radius=12,
                            border_width=1, border_color=mix(BORDER, CYAN, 0.5), fg_color=mix(CARD, CYAN, 0.06),
                            hover_color=mix(CARD, CYAN, 0.16), text_color=CYAN_TEXT, font=self.F.b(12, strong=True),
                            image=ctk.CTkImage(simple_icon("upload", CYAN_TEXT, 64), size=(30, 30)),
                            command=self.upload_image)
        add.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        files = my_cursor_files()
        for i, f in enumerate(files, start=2):
            try:
                frames, _hot, _steps = load_cursor_file(str(f))
                th = frames[0].copy()
                th.thumbnail((112, 112), Image.LANCZOS)
                pic = Image.new("RGBA", (112, 112), (0, 0, 0, 0))
                pic.alpha_composite(th, ((112 - th.width) // 2, (112 - th.height) // 2))
            except Exception:
                continue
            name = f.stem if len(f.stem) <= 16 else f.stem[:14] + "…"
            b = ctk.CTkButton(grid, text=name, compound="top", height=94, width=10, corner_radius=12,
                              border_width=1, font=self.F.b(12), image=ctk.CTkImage(pic, size=(56, 56)),
                              command=lambda p=f: self.use_my_cursor(p))
            b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            self.mine_tiles[str(f)] = b
            self.add_star(b, "my:" + f.name)
        if not files:
            ctk.CTkLabel(grid, text=T("Chưa có con trỏ nào. Tự tạo một con trỏ, hoặc bấm \"+ Thêm con trỏ\" "
                                      "để thêm ảnh PNG, GIF hay file .cur, .ani."), font=self.F.b(12), text_color=TEXT2,
                         wraplength=360, justify="left").grid(row=0, column=2, columnspan=3, sticky="w", padx=12)
        self.update_library()

    # ------------------------------------------------------------ Trình tạo con trỏ
    def edit_made_cursor(self):
        img = self.cfg["image"]
        if self.cfg["shape"] == "Ảnh tải lên" and img:
            spec = self.cfg["made_cursors"].get(Path(img).name)
            if spec:
                self.open_maker(spec, Path(img))

    def open_maker(self, spec=None, path=None):
        if getattr(self, "maker_win", None) is not None:
            try:
                self.maker_win.lift()
                return
            except tk.TclError:
                pass
        sp = dict(MAKER_DEFAULT, **(spec or {}))
        sp["ombre"] = list(sp["ombre"])
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        self.maker_win = d
        d.title(T("Tạo con trỏ"))
        d.resizable(False, False)
        d.transient(self.win)
        state = {"job": None, "img": None, "hot": (0, 0)}
        PV = 300

        outer = ctk.CTkFrame(d, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(outer, text=T("TẠO CON TRỎ"), font=self.F.h(22), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(outer, text=T("Chọn hình, chỉnh dáng, màu và viền. Con trỏ được lưu vào mục Của bạn."),
                     font=self.F.b(13), text_color=TEXT2).pack(anchor="w", pady=(0, 12))
        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # --- bên trái: xem trước
        left = self.card(body)
        left.pack(side="left", fill="y", padx=(0, 14))
        cv = tk.Canvas(left, width=PV, height=PV, bg=FIELD, highlightthickness=1, highlightbackground=BORDER,
                       bd=0, cursor="crosshair")
        cv.pack(padx=14, pady=(14, 6))
        for i in range(0, PV, 20):
            cv.create_line(i, 0, i, PV, fill="#151A24")
            cv.create_line(0, i, PV, i, fill="#151A24")
        img_id = cv.create_image(PV // 2, PV // 2)
        hot_ids = [cv.create_line(0, 0, 0, 0, fill=CYAN, width=1) for _ in range(2)]
        ctk.CTkLabel(left, text=T("Bấm vào hình để đặt điểm click"), font=self.F.b(12),
                     text_color=MUTED).pack()
        ctk.CTkButton(left, text=T("Điểm click tự động"), height=28, width=10, corner_radius=8, border_width=1,
                      border_color=BORDER, fg_color="transparent", hover_color="#1A1E29", text_color=TEXT2,
                      font=self.F.b(12), command=lambda: (sp.update(hot=None), redraw())).pack(pady=(4, 8))
        small = tk.Canvas(left, width=PV, height=86, bg=CARD, highlightthickness=0, bd=0)
        small.pack(padx=14, pady=(0, 14))
        small.create_rectangle(PV // 2, 4, PV - 2, 84, fill="#C9BFA8", outline="")
        small.create_rectangle(2, 4, PV // 2, 84, fill="#10141C", outline="")
        small_ids = [small.create_image(x, 44) for x in (40, 105, 190, 255)]
        self.caps(left, "KÍCH THƯỚC THẬT").place(x=16, y=PV + 74)

        # --- bên phải: tùy chọn
        right = ctk.CTkScrollableFrame(body, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=14,
                                       width=470, height=PV + 150, scrollbar_button_color=BORDER,
                                       scrollbar_button_hover_color="#3A4152")
        right.pack(side="left", fill="both", expand=True)
        pad = dict(padx=14)

        self.caps(right, "HÌNH DÁNG").pack(anchor="w", pady=(12, 6), **pad)
        sg = ctk.CTkFrame(right, fg_color="transparent")
        sg.pack(fill="x", **pad)
        for i in range(5):
            sg.grid_columnconfigure(i, weight=1, uniform="m")
        shape_btns = {}
        for i, (key, name, _kind) in enumerate(MAKER_SHAPES):
            th = maker_render(dict(MAKER_SHAPE_DEFAULTS[key], shape=key, color="#C9CFDC", in_w=0, out_w=0,
                                   shadow=False, shine=False, tip=False), 72)[0]
            b = ctk.CTkButton(sg, text=T(name), compound="top", height=70, width=10, corner_radius=10,
                              border_width=1, font=self.F.b(11), image=ctk.CTkImage(th, size=(32, 32)),
                              command=lambda k=key: set_shape(k))
            b.grid(row=i // 5, column=i % 5, sticky="ew", padx=3, pady=3)
            shape_btns[key] = b

        def slider(label, key, lo, hi, steps):
            row = ctk.CTkFrame(right, fg_color="transparent")
            lab = ctk.CTkLabel(row, text=T(label), font=self.F.b(13), text_color=TEXT, width=110, anchor="w")
            lab.pack(side="left")
            sl = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=steps, progress_color=ACCENT,
                               button_color=ACCENT, button_hover_color=mix(ACCENT, "#FFFFFF", 0.25),
                               fg_color="#1A1E29", height=16, command=lambda v, k=key: (sp.update({k: v}), redraw()))
            sl.pack(side="left", fill="x", expand=True)
            sl.set(sp[key])
            return row, lab, sl

        self.caps(right, "DÁNG").pack(anchor="w", pady=(14, 4), **pad)
        sliders = {
            "width": slider("Độ rộng", "width", 0.4, 1.6, 60),
            "tail": slider("Độ dài đuôi", "tail", 0.0, 1.0, 50),
            "thick": slider("Độ dày nét", "thick", 0.0, 1.0, 50),
            "round": slider("Bo góc", "round", 0.0, 1.0, 50),
            "rot": slider("Xoay", "rot", -60, 60, 120),
        }

        self.caps(right, "TÔ MÀU").pack(anchor="w", pady=(14, 6), **pad)
        fill_map = {T("Một màu"): "solid", "Ombre": "ombre", T("Kính mờ"): "glass"}
        fill_seg = ctk.CTkSegmentedButton(right, values=list(fill_map), height=32, font=self.F.b(12, strong=True),
                                          fg_color=FIELD, unselected_color=FIELD, unselected_hover_color="#1A1E29",
                                          selected_color=mix(CARD, ACCENT, 0.35),
                                          selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT,
                                          command=lambda v: (sp.update(fill=fill_map[v]), redraw()))
        fill_seg.pack(anchor="w", **pad)
        fill_seg.set({v: k for k, v in fill_map.items()}[sp["fill"]])
        color_row = ctk.CTkFrame(right, fg_color="transparent")
        color_row.pack(fill="x", pady=(8, 0), **pad)
        sw_btns = {}
        for c, _n in SWATCHES:
            b = ctk.CTkButton(color_row, text="", width=28, height=28, corner_radius=14, fg_color=c,
                              hover_color=mix(c, "#FFFFFF", 0.2), border_width=0,
                              command=lambda c=c: (sp.update(color=c), redraw()))
            b.pack(side="left", padx=(0, 6))
            sw_btns[c] = b

        def pick_main():
            res = colorchooser.askcolor(color=sp["color"], parent=d, title=T("Chọn màu"))
            if res and res[1]:
                sp["color"] = res[1].upper()
                redraw()

        ctk.CTkButton(color_row, text="", width=28, height=28, corner_radius=14, fg_color="transparent",
                      hover_color="#1A1E29", border_width=1, border_color="#4A5266",
                      image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(12, 12)),
                      command=pick_main).pack(side="left")
        ombre_row = ctk.CTkFrame(right, fg_color="transparent")
        ombre_row.pack(fill="x", pady=(8, 0), **pad)
        ombre_lbls = {}
        for key, _n, cols in OMBRE_PRESETS:
            lb = ctk.CTkLabel(ombre_row, text="", width=28, height=28, cursor="hand2",
                              image=ctk.CTkImage(ombre_dot(cols, False), size=(28, 28)))
            lb.bind("<Button-1>", lambda e, cl=cols: (sp.update(ombre=list(cl), fill="ombre"), redraw()))
            lb.pack(side="left", padx=(0, 6))
            ombre_lbls[key] = lb

        self.caps(right, "VIỀN").pack(anchor="w", pady=(14, 4), **pad)
        edge_btns = {}

        def edge_row(label, ckey, wkey):
            row = ctk.CTkFrame(right, fg_color="transparent")
            row.pack(fill="x", pady=3, **pad)
            ctk.CTkLabel(row, text=T(label), font=self.F.b(13), text_color=TEXT, width=110,
                         anchor="w").pack(side="left")

            def pick():
                res = colorchooser.askcolor(color=sp[ckey], parent=d, title=T("Chọn màu"))
                if res and res[1]:
                    sp[ckey] = res[1].upper()
                    redraw()

            b = ctk.CTkButton(row, text="", width=28, height=28, corner_radius=14, border_width=2,
                              border_color="#4A5266", command=pick)
            b.pack(side="left", padx=(0, 10))
            edge_btns[ckey] = b
            sl = ctk.CTkSlider(row, from_=0, to=14, number_of_steps=14, progress_color=ACCENT, button_color=ACCENT,
                               button_hover_color=mix(ACCENT, "#FFFFFF", 0.25), fg_color="#1A1E29", height=16,
                               command=lambda v: (sp.update({wkey: int(v)}), redraw()))
            sl.pack(side="left", fill="x", expand=True)
            sl.set(sp[wkey])

        edge_row("Viền trong", "in_col", "in_w")
        edge_row("Viền ngoài", "out_col", "out_w")

        self.caps(right, "CHI TIẾT").pack(anchor="w", pady=(14, 4), **pad)
        det = ctk.CTkFrame(right, fg_color="transparent")
        det.pack(fill="x", pady=(0, 14), **pad)
        for key, label in (("tip", "Chấm sáng ở mũi"), ("shine", "Vệt sáng"), ("shadow", "Bóng đổ")):
            var = tk.BooleanVar(value=sp[key])
            ctk.CTkCheckBox(det, text=T(label), variable=var, font=self.F.b(13), text_color=TEXT, checkbox_width=20,
                            checkbox_height=20, corner_radius=6, border_width=1, fg_color=ACCENT, hover_color=ACCENT,
                            border_color="#4A5266", checkmark_color="#FFFFFF",
                            command=lambda k=key, v=var: (sp.update({k: bool(v.get())}), redraw())
                            ).pack(side="left", padx=(0, 16))

        # --- dưới cùng: tên + lưu
        foot = ctk.CTkFrame(outer, fg_color="transparent")
        foot.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(foot, text=T("Tên"), font=self.F.b(13), text_color=TEXT2).pack(side="left", padx=(0, 8))
        name_var = tk.StringVar(value=path.stem if path else T("Con trỏ của tôi"))
        ctk.CTkEntry(foot, textvariable=name_var, width=240, height=38, corner_radius=10, border_color=BORDER,
                     fg_color=FIELD, text_color=TEXT, font=self.F.b(13)).pack(side="left")

        def close():
            self.maker_win = None
            try:
                d.destroy()
            except tk.TclError:
                pass

        def save():
            im, hot = maker_render(sp)
            data = png_to_cur(im, hot)
            try:
                MY_DIR.mkdir(parents=True, exist_ok=True)
                name = name_var.get().strip() or T("Con trỏ của tôi")
                dest = path if path is not None and Path(path).exists() else unique_my_path(name + ".cur")
                Path(dest).write_bytes(data)
            except OSError as e:
                messagebox.showerror(T("Lỗi"), T("Không lưu được con trỏ:") + f"\n{e}", parent=d)
                return
            keep = {k: sp[k] for k in MAKER_DEFAULT}
            self.cfg["made_cursors"] = dict(self.cfg["made_cursors"], **{Path(dest).name: keep})
            self.img_cache.clear()
            close()
            self.rebuild_mine_tiles()
            self.cfg["tint_image"] = False          # con trỏ tự tạo giữ đúng màu đã chọn
            self.cfg["ombre"] = False
            try:
                self.tint_var.set(False)
            except AttributeError:
                pass
            self.use_my_cursor(dest)
            self.save()

        ctk.CTkButton(foot, text=T("Lưu vào Của bạn"), command=save, height=42, width=170, corner_radius=10,
                      fg_color=ACCENT, hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF",
                      font=self.F.h(14)).pack(side="right")
        ctk.CTkButton(foot, text=T("Hủy"), command=close, width=90, height=42, corner_radius=10,
                      fg_color="transparent", hover_color="#1A1E29", text_color=TEXT2,
                      font=self.F.b(13)).pack(side="right", padx=(0, 8))

        # --- vẽ lại
        def set_shape(key):
            sp.update(MAKER_SHAPE_DEFAULTS[key], shape=key, hot=None)
            for k, (_row, _lab, sl) in sliders.items():
                sl.set(sp[k])
            redraw()

        def render_now():
            state["job"] = None
            try:
                im, hot = maker_render(sp)
            except Exception:
                self.report_error("maker", once=True)
                return
            state["img"], state["hot"] = im, hot
            S = 240
            ph = ImageTk.PhotoImage(im.resize((S, S), Image.LANCZOS), master=self.ov)
            cv.itemconfig(img_id, image=ph)
            cv._ph = ph
            off = (PV - S) // 2
            hx, hy = off + hot[0] * S / 256, off + hot[1] * S / 256
            cv.coords(hot_ids[0], hx - 9, hy, hx + 10, hy)
            cv.coords(hot_ids[1], hx, hy - 9, hx, hy + 10)
            phs = []
            for idx, size in enumerate((32, 48, 32, 48)):
                p2 = ImageTk.PhotoImage(im.resize((size, size), Image.LANCZOS), master=self.ov)
                small.itemconfig(small_ids[idx], image=p2)
                phs.append(p2)
            small._ph = phs
            # trạng thái các nút
            kind = dict((a, c) for a, _, c in MAKER_SHAPES)[sp["shape"]]
            for k, b in shape_btns.items():
                on = k == sp["shape"]
                b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD, border_color=ACCENT if on else BORDER,
                            hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                            text_color="#FFFFFF" if on else TEXT2)
            show = {"width": True, "rot": sp["shape"] not in ("dot", "ring"),
                    "tail": kind == "poly" or sp["shape"] == "cross",
                    "thick": sp["shape"] in ("ring", "cross"), "round": kind == "poly"}
            want = [k for k in sliders if show[k]]
            if want != state.get("rows"):
                state["rows"] = want
                for k, (row, _lab, _sl) in sliders.items():
                    row.pack_forget()
                for k in want:
                    sliders[k][0].pack(fill="x", pady=3, padx=14, before=sliders_anchor)
            sliders["tail"][1].configure(text=T("Khe hở") if sp["shape"] == "cross" else T("Độ dài đuôi"))
            for c, b in sw_btns.items():
                on = sp["fill"] != "ombre" and c.lower() == sp["color"].lower()
                b.configure(border_width=3 if on else 0, border_color="#FFFFFF")
            cur = [x.lower() for x in sp["ombre"]]
            for key, _n, cols in OMBRE_PRESETS:
                on = sp["fill"] == "ombre" and [x.lower() for x in cols] == cur
                ombre_lbls[key].configure(image=ctk.CTkImage(ombre_dot(cols, on), size=(28, 28)))
            for ckey, b in edge_btns.items():
                b.configure(fg_color=sp[ckey], hover_color=sp[ckey])
            fill_seg.set({v: k for k, v in fill_map.items()}[sp["fill"]])

        def redraw():
            if state["job"] is None:
                state["job"] = d.after(40, render_now)

        def on_click(e):
            S = 240
            off = (PV - S) // 2
            x, y = (e.x - off) * 256 / S, (e.y - off) * 256 / S
            if 0 <= x < 256 and 0 <= y < 256:
                sp["hot"] = [int(x), int(y)]
                redraw()

        cv.bind("<Button-1>", on_click)
        # các hàng thanh trượt nằm trước nhãn TÔ MÀU
        sliders_anchor = [w for w in right.winfo_children() if isinstance(w, ctk.CTkLabel)
                          and w.cget("text") == T("TÔ MÀU")][0]
        d.protocol("WM_DELETE_WINDOW", close)
        render_now()
        try:
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 4
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)

    # ------------------------------------------------------------ Kho con trỏ trực tuyến
    def cat_file(self, cid):
        name = self.cfg["catalog_got"].get(cid)
        if not name:
            return None
        f = MY_DIR / name
        return f if f.is_file() else None

    def cat_thumb_path(self, e):
        return CAT_DIR / f"{e['id']}-{e['sha256'][:8]}.png"

    def start_catalog(self, force=False):
        if self.cat_busy:
            return
        self.cat_busy = True
        self.cat_status = ("loading", 0)
        self.update_cat_label()

        def work():
            try:
                data = json.loads(http_get(CATALOG_URL, 512 * 1024).decode("utf-8"))
                entries = clean_catalog(data)
                try:
                    CAT_DIR.mkdir(parents=True, exist_ok=True)
                    (CAT_DIR / "catalog.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
                self.q.put(("cat_list", entries, True))
                self.fetch_thumbs(entries)
            except Exception as ex:
                log.warning("Kho trực tuyến: %s", ex)
                self.q.put(("cat_error", str(ex)))
            finally:
                self.q.put(("cat_end",))

        threading.Thread(target=work, daemon=True).start()

    def fetch_thumbs(self, entries):
        for e in entries:
            path = self.cat_thumb_path(e)
            if path.exists():
                continue
            try:
                data = http_get(urllib.parse.urljoin(CATALOG_URL, e["thumb"]), 512 * 1024)
                Image.open(io.BytesIO(data)).verify()
                path.write_bytes(data)
                self.q.put(("cat_thumb", e["id"]))
            except Exception as ex:
                log.warning("Ảnh nhỏ %s: %s", e["id"], ex)

    def handle_catalog(self, cmd, *args):
        if cmd == "cat_list":
            entries, online = args
            self.cat_entries = entries
            self.cat_status = ("ok" if online else "offline", len(entries))
            self.build_online_tiles()
        elif cmd == "cat_error":
            if self.cat_entries is None:
                try:
                    data = json.loads((CAT_DIR / "catalog.json").read_text(encoding="utf-8"))
                    self.handle_catalog("cat_list", clean_catalog(data), False)
                    return
                except Exception:
                    pass
            if self.cat_status[0] != "offline":
                self.cat_status = ("error", 0)
        elif cmd == "cat_end":
            self.cat_busy = False
        elif cmd == "cat_thumb":
            self.set_cat_tile(args[0])
        elif cmd == "cat_done":
            cid, path = args
            self.cat_dl.discard(cid)
            self.cfg["catalog_got"] = dict(self.cfg["catalog_got"], **{cid: Path(path).name})
            self.rebuild_mine_tiles()
            self.use_my_cursor(path)
            self.set_cat_tile(cid)
            self.save()
        elif cmd == "cat_fail":
            cid, msg = args
            self.cat_dl.discard(cid)
            self.set_cat_tile(cid)
            messagebox.showerror(APP_NAME, T("Không tải được con trỏ:") + f"\n{T(msg)}", parent=self.win)
        self.update_cat_label()

    def update_cat_label(self):
        kind, n = self.cat_status
        txt = {"loading": T("Đang tải danh sách…"),
               "ok": T("{n} con trỏ · Bấm để tải về, con trỏ sẽ nằm trong mục Của bạn.").format(n=n),
               "offline": T("Đang xem danh sách lưu lần trước (chưa kết nối được)."),
               "error": T("Không kết nối được kho trực tuyến. Kiểm tra mạng rồi bấm Làm mới.")}.get(kind, "")
        try:
            self.cat_label.configure(text=txt, text_color=AMBER if kind in ("error", "offline") else TEXT2)
        except (tk.TclError, AttributeError):
            pass

    def build_online_tiles(self):
        grid = getattr(self, "lib_grids", {}).get("online")
        if grid is None:
            return
        for w in grid.winfo_children():
            w.destroy()
        self.cat_tiles = {}
        cols = 5
        today = time.strftime("%Y-%m-%d")
        for i, e in enumerate(self.cat_entries or []):
            b = ctk.CTkButton(grid, text="", compound="top", height=104, width=10, corner_radius=12,
                              border_width=1, font=self.F.b(12), command=lambda e=e: self.online_pick(e))
            b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            self.cat_tiles[e["id"]] = b
            try:
                age = (time.mktime(time.strptime(today, "%Y-%m-%d"))
                       - time.mktime(time.strptime(e["added"], "%Y-%m-%d"))) / 86400
            except ValueError:
                age = 999
            if age <= 30:
                ctk.CTkLabel(b, text=T("MỚI"), font=self.F.m(9), text_color="#0B0D12", fg_color=GREEN,
                             corner_radius=6, height=16, width=10).place(x=8, y=7)
            self.set_cat_tile(e["id"])
        self.update_cat_label()
        self.update_library()

    def set_cat_tile(self, cid):
        b = getattr(self, "cat_tiles", {}).get(cid)
        e = next((x for x in self.cat_entries or [] if x["id"] == cid), None)
        if b is None or e is None:
            return
        name = catalog_name(e)
        name = name if len(name) <= 18 else name[:16] + "…"
        state = (T("Đang tải…") if cid in self.cat_dl else T("✓ Đã có") if self.cat_file(cid) else T("Tải về"))
        img = self.cat_thumbs.get(cid)
        if img is None:
            try:
                pic = Image.open(self.cat_thumb_path(e)).convert("RGBA")
                img = self.cat_thumbs[cid] = ctk.CTkImage(pic, size=(56, 56))
            except Exception:
                img = ctk.CTkImage(Image.new("RGBA", (112, 112), (0, 0, 0, 0)), size=(56, 56))
        try:
            b.configure(text=f"{name}\n{state}", image=img)
        except tk.TclError:
            pass

    def online_pick(self, e):
        cid = e["id"]
        f = self.cat_file(cid)
        if f is not None:
            self.use_my_cursor(f)
            return
        if cid in self.cat_dl:
            return
        self.cat_dl.add(cid)
        self.set_cat_tile(cid)
        name = catalog_name(e)

        def work():
            try:
                data = http_get(urllib.parse.urljoin(CATALOG_URL, e["file"]), min(e["size"] + 1024, CAT_MAX))
                if hashlib.sha256(data).hexdigest() != e["sha256"]:
                    raise ValueError("File không khớp mã kiểm tra")
                MY_DIR.mkdir(parents=True, exist_ok=True)
                dest = unique_my_path(name + Path(e["file"]).suffix.lower())
                dest.write_bytes(data)
                try:
                    load_cursor_file(str(dest))
                except Exception:
                    dest.unlink()
                    raise ValueError("File con trỏ bị lỗi")
                self.q.put(("cat_done", cid, str(dest)))
            except Exception as ex:
                log.warning("Tải %s: %s", cid, ex)
                self.q.put(("cat_fail", cid, str(ex)))

        threading.Thread(target=work, daemon=True).start()

    def set_mine_tint(self, on):
        self.cfg["tint_image"] = on
        self.cfg["ombre"] = False
        try:
            self.tint_var.set(on)
        except AttributeError:
            pass
        self.refresh()

    def show_lib_view(self):
        v = self.lib_view
        for view, row in self.chip_rows.items():
            row.pack_forget()
        self.chip_rows[v].pack(fill="x", pady=(6, 0))
        if v == "online":
            self.theme_caps.pack_forget()
        else:
            self.theme_caps.pack(anchor="w", before=self.chip_rows[v])
        try:
            self.view_seg.set({k2: k for k, k2 in self.view_map.items()}[v])
        except (KeyError, tk.TclError):
            pass
        for view, g in self.lib_grids.items():
            g.pack_forget()
        self.lib_grids[v].pack(fill="both", expand=True, padx=10, pady=10)
        if v == "bibata":
            self.bib_opts.pack(side="right", anchor="e")
            self.bib_link.pack(side="right")
        else:
            self.bib_opts.pack_forget()
            self.bib_link.pack_forget()
        if v == "mine":
            self.mine_del.pack(side="right")
            self.mine_edit.pack(side="right", padx=(0, 8))
        else:
            self.mine_del.pack_forget()
            self.mine_edit.pack_forget()
        if v == "online":
            self.sw_caps.pack_forget()
            self.sw_row.pack_forget()
            if self.cat_entries is None and not self.cat_busy:
                self.start_catalog()
        elif not self.sw_row.winfo_ismapped():
            self.sw_caps.pack(anchor="w", pady=(12, 0), before=self.lib_card)
            self.sw_row.pack(fill="x", pady=(6, 12), before=self.lib_card)

    def set_lib_view(self, view):
        self.lib_view = view
        self.show_lib_view()
        self.update_library()

    def set_own_theme(self, theme):
        self.cfg["own_theme"] = theme
        self.cfg["ombre"] = False
        if self.cfg["shape"] not in OWN_BY_ID:
            self.cfg["shape"] = "EzDrop"
        self.refresh()

    def set_bib_color(self, color):
        self.cfg["color"] = color
        self.cfg["ombre"] = False
        if self.lib_view == "mine":
            self.set_mine_tint(True)
            return
        if self.lib_view == "ez":
            self.cfg["own_theme"] = "custom"
            if self.cfg["shape"] not in OWN_BY_ID:
                self.cfg["shape"] = "EzDrop"
        else:
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
        if key == "bibata_theme":
            self.cfg["ombre"] = False
        if key == "bibata_theme" and self.cfg["shape"] != "Bibata":
            self.cfg["shape"] = "Bibata"
        self.refresh()

    # ------------------------------------------------------------ Con trỏ yêu thích
    def add_star(self, tile, fid):
        if not hasattr(self, "star_imgs"):
            self.star_imgs = {True: ctk.CTkImage(star_icon(True, "#FFC940", 32), size=(15, 15)),
                              False: ctk.CTkImage(star_icon(False, "#6B7488", 32), size=(15, 15))}
        sb = ctk.CTkButton(tile, text="", width=24, height=24, corner_radius=7, fg_color="transparent",
                           hover_color="#2A3040", border_width=0, image=self.star_imgs[False],
                           command=lambda: self.toggle_fav(fid))
        sb.place(relx=1.0, x=-5, y=5, anchor="ne")
        self.star_btns[fid] = sb

    def toggle_fav(self, fid):
        favs = list(self.cfg["favorites"])
        if fid in favs:
            favs.remove(fid)
        else:
            favs.append(fid)
        self.cfg["favorites"] = favs
        self.update_library()
        self.save()

    def fav_valid(self, fid):
        if fid.startswith("bib:"):
            return BIBATA_DIR.exists() and fid[4:] in dict(BIBATA_CURSORS)
        if fid.startswith("my:"):
            return (MY_DIR / fid[3:]).is_file()
        return fid in OWN_BY_ID and own_image(fid) is not None

    def fav_label(self, fid):
        if fid.startswith("bib:"):
            return "Bibata · " + T(dict(BIBATA_CURSORS).get(fid[4:], fid[4:]))
        if fid.startswith("my:"):
            return Path(fid[3:]).stem
        return T(OWN_BY_ID[fid][1]) if fid in OWN_BY_ID else T(fid)

    def current_fav_id(self):
        c = self.cfg
        if c["shape"] == "Bibata":
            return "bib:" + c["bibata_cursor"]
        if c["shape"] == "Ảnh tải lên":
            return "my:" + Path(c["image"]).name if c["image"] and Path(c["image"]).parent == MY_DIR else None
        return c["shape"]

    def use_fav(self, fid):
        if not self.fav_valid(fid):
            return
        if fid.startswith("bib:"):
            self.pick_bibata(fid[4:])
        elif fid.startswith("my:"):
            self.use_my_cursor(MY_DIR / fid[3:])
        else:
            self.set_shape(fid)

    def pick_own(self, shape):
        self.cfg["shape"] = shape
        self.refresh()

    def pick_bibata(self, name):
        self.cfg["bibata_cursor"] = name
        self.cfg["shape"] = "Bibata"
        self.refresh()

    @staticmethod
    def _chip_dot(col):
        return ctk.CTkImage(_ss(lambda d, s, col=col: d.ellipse(
            [1 * s, 1 * s, 15 * s, 15 * s], fill=col, outline="#FFFFFF", width=int(1.5 * s)), 16), size=(14, 14))

    def _chip_style(self, b, on, image):
        b.configure(image=image, fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                    hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                    border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)

    def update_library(self):
        self._update_library()
        c = self.cfg
        oimg = ctk.CTkImage(ombre_swatch(c["ombre_colors"], 32), size=(16, 16))
        for b in getattr(self, "ombre_chips", []):
            try:
                self._chip_style(b, c["ombre"], oimg)
            except tk.TclError:
                pass
        for sb in getattr(self, "star_btns", {}).values():
            try:
                col = sb.master.cget("fg_color")
                hov = sb.master.cget("hover_color")
                if getattr(sb, "_bg", None) != col:
                    sb._bg = col
                    sb.configure(fg_color=col, bg_color=col, hover_color=hov)
            except (tk.TclError, ValueError):
                pass

    def _update_library(self):
        if getattr(self, "bib_swatches", None) is None:
            return
        c = self.cfg
        view = self.lib_view
        for key, b in self.own_theme_buttons.items():
            img = (ctk.CTkImage(own_image("EzDrop").resize((32, 32), Image.LANCZOS), size=(16, 16))
                   if key == "original" and own_image("EzDrop") is not None else self._chip_dot(c["color"]))
            self._chip_style(b, key == c["own_theme"] and not c["ombre"], img)
        for key, b in self.theme_buttons.items():
            col = BIBATA_THEMES[key][1] if key in BIBATA_THEMES else c["color"]
            self._chip_style(b, key == c["bibata_theme"] and not c["ombre"], self._chip_dot(col))
        for key, b in getattr(self, "mine_theme_buttons", {}).items():
            img = (self._chip_dot(c["color"]) if key == "tint" or own_image("EzDrop") is None
                   else ctk.CTkImage(own_image("EzDrop").resize((32, 32), Image.LANCZOS), size=(16, 16)))
            self._chip_style(b, (key == "tint") == bool(c["tint_image"]) and not c["ombre"], img)
        favs = set(c["favorites"])
        for fid, sb in getattr(self, "star_btns", {}).items():
            on = fid in favs
            if getattr(sb, "_fav_on", None) != on:
                sb._fav_on = on
                try:
                    sb.configure(image=self.star_imgs[on])
                except tk.TclError:
                    pass
        mine_sel = c["image"] if c["shape"] == "Ảnh tải lên" else None
        for path, b in getattr(self, "mine_tiles", {}).items():
            on = path == mine_sel
            b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)
        for cid, b in getattr(self, "cat_tiles", {}).items():
            f = self.cat_file(cid)
            on = mine_sel is not None and f is not None and Path(mine_sel) == f
            try:
                b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                            hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                            border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)
            except tk.TclError:
                pass
        if getattr(self, "mine_del", None):
            self.mine_del.configure(state="normal" if mine_sel and mine_sel in self.mine_tiles else "disabled")
            made = mine_sel and mine_sel in self.mine_tiles and Path(mine_sel).name in c["made_cursors"]
            self.mine_edit.configure(state="normal" if made else "disabled")
        custom_on = {"ez": c["own_theme"] == "custom", "bibata": c["bibata_theme"] == "custom",
                     "mine": bool(c["tint_image"])}.get(view, False) and not c["ombre"]
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
        # hình trên ô: chỉ vẽ lại khi đổi chủ đề / màu
        oc = tuple(c["ombre_colors"]) if c["ombre"] else None
        osig = (c["own_theme"], c["color"].lower() if c["own_theme"] == "custom" else "", oc)
        if osig != self._own_sig:
            self._own_sig = osig
            for shape, b in self.own_tiles.items():
                if oc:
                    im = own_image(shape).resize((112, 112), Image.LANCZOS)
                    hx, hy = OWN_BY_ID[shape][3]
                    im = apply_ombre(im, ombre_tmap(im, (hx * 112 // 256, hy * 112 // 256)), ombre_lut(oc))
                else:
                    im = own_image_colored(shape, c["color"]) if c["own_theme"] == "custom" else own_image(shape)
                    im = im.resize((112, 112), Image.LANCZOS)
                b.configure(image=ctk.CTkImage(im, size=(56, 56)))
        if self.bib_tiles:
            variant = self.bibata_variant()
            colors = bibata_colors("custom" if oc else c["bibata_theme"], oc[0] if oc else c["color"])
            sig = (variant, colors, oc)
            if sig != self._lib_sig:
                self._lib_sig = sig
                for name, b in self.bib_tiles.items():
                    im = bibata_image(BIBATA_DIR, variant, name, colors).resize((112, 112), Image.LANCZOS)
                    if oc:
                        hx, hy = BIBATA_META["hotspots"].get(f"{variant}/{name}", [128, 128])
                        im = apply_ombre(im, ombre_tmap(im, (hx * 112 // 256, hy * 112 // 256)), ombre_lut(oc))
                    b.configure(image=ctk.CTkImage(im, size=(56, 56)))
        tile_bg = mix(FIELD, "#FFFFFF", 0.05) if c["bibata_theme"] == "classic" else FIELD
        for shape, tile in self.own_tiles.items():
            on = c["shape"] == shape
            tile.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                           hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                           border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT)
        for name, b in self.bib_tiles.items():
            on = c["shape"] == "Bibata" and name == c["bibata_cursor"]
            b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else tile_bg,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)

    # ------------------------------------------------------------ Tab Hiệu ứng
    def build_fx_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.page_top(page, "HIỆU ỨNG", "Thêm vệt sáng theo con trỏ và hiệu ứng khi click trong game.", (0, 14))
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
        row.pack(fill="x", padx=16, pady=(6, 6))
        ctk.CTkLabel(row, text=T("Mật độ"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.fx_dens_seg = ctk.CTkSegmentedButton(row, values=list(self.fx_dens_map),
                                                  command=lambda v: self.set_fx("fx_density", self.fx_dens_map[v]), **seg_kw)
        self.fx_dens_seg.pack(side="right")
        row = ctk.CTkFrame(opt, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 12))
        ctk.CTkLabel(row, text=T("Viền khi giữ chuột"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.hold_vars, self.hold_btns = {}, {}
        for side, label in (("right", "Phải"), ("left", "Trái")):     # xếp từ phải sang
            btn = ctk.CTkButton(row, text="", width=26, height=26, corner_radius=13, border_width=2,
                                border_color="#FFFFFF", fg_color=self.cfg[f"hold_{side}_color"],
                                hover_color=self.cfg[f"hold_{side}_color"],
                                command=lambda sd=side: self.pick_hold_color(sd))
            btn.pack(side="right", padx=(6, 18 if side == "left" else 0))
            var = tk.BooleanVar(value=self.cfg[f"hold_{side}"])
            ctk.CTkCheckBox(row, text=T(label), variable=var, width=10, checkbox_width=20, checkbox_height=20,
                            corner_radius=6, border_width=1, fg_color=ACCENT, hover_color=ACCENT,
                            border_color="#4A5266", checkmark_color="#FFFFFF", font=self.F.b(12),
                            text_color=TEXT, command=lambda sd=side: self.set_hold_opt(sd)).pack(
                side="right")
            self.hold_vars[side], self.hold_btns[side] = var, btn

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

    def set_hold_opt(self, side):
        self.cfg[f"hold_{side}"] = bool(self.hold_vars[side].get())
        self.refresh()

    def pick_hold_color(self, side):
        res = colorchooser.askcolor(color=self.cfg[f"hold_{side}_color"], parent=self.win, title=T("Chọn màu viền"))
        if res and res[1]:
            self.cfg[f"hold_{side}_color"] = res[1]
            self.hold_btns[side].configure(fg_color=res[1], hover_color=res[1])
            if not self.cfg[f"hold_{side}"]:          # chọn màu thì bật luôn
                self.cfg[f"hold_{side}"] = True
                self.hold_vars[side].set(True)
            self.refresh()

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
            if self.find_t0 is not None:
                self.find_frame(now)
            if self.cursor_frames and self.active and not self.system_mode() and now * 1000 >= self.cf_next:
                self.cf_idx = (self.cf_idx + 1) % len(self.cursor_frames)
                self.cf_next = now * 1000 + self.cursor_durations[self.cf_idx]
                self.show_img(self.cursor_frames[self.cf_idx])
            on = c["fx_trail"] != "off" or c["fx_click"] != "off"
            want = on and (self.active or now < self.fx_test_until)
            if want or self.fx.busy():
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                down = mouse_buttons()[0]
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
            if self.quitting:
                return
            self.report_error("fx", once=True)
        except Exception:
            self.report_error("fx", once=True)
        if not self.quitting:
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
        r.pack(fill="x", padx=18, pady=(5, 0))
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
        ctk.CTkFrame(box, fg_color=LINE, height=1, corner_radius=0).pack(fill="x", padx=18, pady=(5, 0))

        if REAL_CURSOR_MODE:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=18, pady=(5, 0))
            t = ctk.CTkFrame(r, fg_color="transparent")
            t.pack(side="left")
            ctk.CTkLabel(t, text=T("Chế độ con trỏ"), font=self.F.b(14, strong=True), text_color=TEXT,
                         height=20).pack(anchor="w")
            self.mode_sub = ctk.CTkLabel(t, text="", font=self.F.b(12), text_color=TEXT2, height=18)
            self.mode_sub.pack(anchor="w")
            self.mode_map = {T("Lớp phủ"): "overlay", T("Con trỏ thật"): "system"}
            self.mode_seg = ctk.CTkSegmentedButton(
                r, values=list(self.mode_map), command=lambda v: self.set_cursor_mode(self.mode_map[v]), height=32,
                font=self.F.b(12, strong=True), fg_color=FIELD, unselected_color=FIELD,
                unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
            self.mode_seg.pack(side="right")
            ctk.CTkFrame(box, fg_color=LINE, height=1, corner_radius=0).pack(fill="x", padx=18, pady=(5, 0))
            self.update_mode_ui()

        self.hide_var = tk.BooleanVar(value=self.cfg["hide_real"])
        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        self.auto_upd_var = tk.BooleanVar(value=self.cfg["auto_check_update"])
        self.splash_var = tk.BooleanVar(value=self.cfg["splash"])
        self.taskbar_var = tk.BooleanVar(value=self.cfg["keep_taskbar"])
        self.predict_var = tk.BooleanVar(value=self.cfg["predict"])
        rows = [("Ẩn con trỏ thật của game", "Chỉ hiện con trỏ của EzCursor khi đang ở trong game.",
                 self.hide_var, self.set_hide),
                ("Khởi động cùng Windows", "Chạy ngầm dưới khay hệ thống khi bật máy.",
                 self.startup_var, self.set_startup_opt),
                ("Tự động kiểm tra cập nhật", "Thông báo khi có phiên bản mới trên GitHub.",
                 self.auto_upd_var, self.set_auto_update),
                ("Giữ con trỏ trên thanh taskbar", "Rê chuột xuống taskbar vẫn dùng con trỏ EzCursor.",
                 self.taskbar_var, self.set_keep_taskbar),
                ("Đoán trước vị trí con trỏ", "Bù thêm nửa khung hình khi rê nhanh; có thể trượt nhẹ khi đổi hướng.",
                 self.predict_var, self.set_predict),
                ("Màn hình chào khi mở", "Hiện logo động khoảng 2 giây mỗi lần mở EzCursor.",
                 self.splash_var, self.set_splash)]
        for title, sub, var, cmd in rows:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=18, pady=(5, 0))
            t = ctk.CTkFrame(r, fg_color="transparent")
            t.pack(side="left")
            ctk.CTkLabel(t, text=T(title), font=self.F.b(14, strong=True), text_color=TEXT, height=20).pack(anchor="w")
            ctk.CTkLabel(t, text=T(sub), font=self.F.b(12), text_color=TEXT2, height=18).pack(anchor="w")
            self.switch(r, var, cmd).pack(side="right")
            ctk.CTkFrame(box, fg_color=LINE, height=1, corner_radius=0).pack(fill="x", padx=18, pady=(5, 0))

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
        ctk.CTkButton(r, text=T("Khôi phục cài đặt gốc"), command=self.reset_settings, height=40, width=10,
                      corner_radius=10, border_width=1, border_color="#FF5A5A", fg_color=mix(CARD, "#FF5A5A", 0.10),
                      hover_color=mix(CARD, "#FF5A5A", 0.22), text_color="#FF8A8A",
                      font=self.F.b(13, strong=True)).pack(side="right")
        self.cyan_button(r, "Kiểm tra cập nhật", lambda: self.check_update(manual=True)).pack(side="right", padx=(0, 8))
        self.cyan_button(r, "Mở thư mục log", self.open_log_folder).pack(side="right", padx=(0, 8))

        hk = self.card(page)
        hk.pack(fill="x", pady=(12, 0))
        head = ctk.CTkFrame(hk, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(10, 4))
        self.caps(head, "PHÍM TẮT").pack(side="left")
        ctk.CTkButton(head, text=T("Mặc định"), command=self.reset_hotkeys, width=10, height=24, corner_radius=6,
                      fg_color="transparent", hover_color="#1A1E29", text_color=MUTED,
                      font=self.F.b(12)).pack(side="right")
        ctk.CTkLabel(head, text=T("Bấm vào một ô để đổi phím"), font=self.F.b(12),
                     text_color=MUTED).pack(side="right", padx=8)
        grid = ctk.CTkFrame(hk, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 12))
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="h")
        self.hotkey_caps = {}
        keys = [("toggle", "Bật / tắt"), ("shape", "Đổi hình dạng"), ("color", "Đổi màu"), ("quit", "Thoát"),
                ("find", "Tìm con trỏ")]
        for i, (act, desc) in enumerate(keys):
            cell = ctk.CTkFrame(grid, fg_color=FIELD, border_color=LINE, border_width=1, corner_radius=10,
                                cursor="hand2")
            cell.grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
            lbl = ctk.CTkLabel(cell, text=T(desc), font=self.F.b(13), text_color="#C9CFDB")
            lbl.pack(side="left", padx=(12, 4), pady=10)
            caps = ctk.CTkFrame(cell, fg_color="transparent")
            caps.pack(side="right", padx=(0, 8))
            self.hotkey_caps[act] = caps
            for w in (cell, lbl, caps):
                w.bind("<Button-1>", lambda e, a=act: self.capture_hotkey(a))
                w.bind("<Enter>", lambda e, c=cell: c.configure(border_color=ACCENT))
                w.bind("<Leave>", lambda e, c=cell: c.configure(border_color=LINE))
        cell = ctk.CTkFrame(grid, fg_color=FIELD, border_color=LINE, border_width=1, corner_radius=10)
        cell.grid(row=1, column=2, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(cell, text=T("Lắc chuột để tìm"), font=self.F.b(13), text_color="#C9CFDB").pack(
            side="left", padx=(12, 4), pady=10)
        self.shake_var = tk.BooleanVar(value=self.cfg["find_shake"])
        self.switch(cell, self.shake_var, self.set_find_shake).pack(side="right", padx=(0, 8))
        self.update_hotkey_ui()
        return page

    def set_find_shake(self):
        self.cfg["find_shake"] = bool(self.shake_var.get())
        self.sh_rev = []
        self.save()

    # ------------------------------------------------------------ Phím tắt
    def update_hotkey_ui(self):
        hk = self.cfg["hotkeys"]
        for act, caps in getattr(self, "hotkey_caps", {}).items():
            for w in caps.winfo_children():
                w.destroy()
            for key in hotkey_parts(hk[act], act):
                k = ctk.CTkLabel(caps, text=key, font=self.F.m(11), text_color=TEXT, fg_color="#181C26",
                                 corner_radius=6, width=10, height=24)
                k.pack(side="left", padx=2)
                k.bind("<Button-1>", lambda e, a=act: self.capture_hotkey(a))
        if getattr(self, "toggle_hint", None):
            self.toggle_hint.configure(text=" + ".join(hotkey_parts(hk["toggle"], "toggle")))

    def reset_hotkeys(self):
        self.cfg["hotkeys"] = json.loads(json.dumps(DEFAULT_CFG["hotkeys"]))
        self.update_hotkey_ui()
        self.save()

    def hotkey_conflict(self, act, new):
        """Tên hành động đang dùng tổ hợp phím này (nếu trùng)."""
        names = {"toggle": "Bật / tắt", "shape": "Đổi hình dạng", "color": "Đổi màu", "quit": "Thoát",
                 "find": "Tìm con trỏ"}
        combos = {}
        for a, b in self.cfg["hotkeys"].items():
            b = new if a == act else b
            mods = frozenset(b["mods"])
            vks = range(0x31, 0x36) if a == "color" else [b["vk"]]
            for vk in vks:
                if (mods, vk) in combos and a != combos[(mods, vk)]:
                    other = combos[(mods, vk)]
                    return T(names[other if other != act else a])
                combos[(mods, vk)] = a
        return None

    def capture_hotkey(self, act):
        """Hộp thoại nhỏ chờ người dùng bấm tổ hợp phím mới."""
        if self.capturing:
            return
        self.capturing = True
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        d.title(T("Đổi phím tắt"))
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.transient(self.win)
        frm = ctk.CTkFrame(d, fg_color="transparent")
        frm.pack(fill="both", padx=22, pady=18)
        hint = (T("Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím số từ 1 đến 5.") if act == "color"
                else T("Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím chữ, số hoặc F1–F12."))
        ctk.CTkLabel(frm, text=T("Nhấn tổ hợp phím mới"), font=self.F.h(18), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(frm, text=hint, font=self.F.b(12), text_color=TEXT2, wraplength=360,
                     justify="left").pack(anchor="w", pady=(4, 12))
        live = ctk.CTkLabel(frm, text="…", font=self.F.m(16), text_color=ACCENT, height=36)
        live.pack(anchor="w")
        msg = ctk.CTkLabel(frm, text=T("Bấm Esc để hủy."), font=self.F.b(12), text_color=MUTED)
        msg.pack(anchor="w", pady=(8, 0))
        state = {"seen_clear": False}

        def close():
            self.capturing = False
            self.prev_keys = {"*"}          # tránh kích hoạt phím vừa bấm
            try:
                d.destroy()
            except tk.TclError:
                pass

        def poll():
            if not d.winfo_exists():
                self.capturing = False
                return
            mods = mods_down()
            keys = [vk for vk in HOTKEY_VKS if key_down(vk)]
            if not mods and not keys:
                state["seen_clear"] = True
            if key_down(0x1B):              # Esc
                close()
                return
            labels = [label for m, _, label in HOTKEY_MODS if m in mods]
            live.configure(text=" + ".join(labels + [vk_name(k) for k in keys[:1]]) or "…")
            if state["seen_clear"] and keys:
                vk = keys[0]
                if not ({"ctrl", "alt"} & mods):
                    msg.configure(text=T("Cần giữ Ctrl hoặc Alt."), text_color=AMBER)
                elif act == "color" and not 0x31 <= vk <= 0x35:
                    msg.configure(text=T("Đổi màu dùng các phím số 1–5."), text_color=AMBER)
                else:
                    new = {"mods": [m for m, _, _ in HOTKEY_MODS if m in mods]}
                    if act != "color":
                        new["vk"] = vk
                    other = self.hotkey_conflict(act, new)
                    if other:
                        msg.configure(text=T("Trùng với phím của: ") + other, text_color=AMBER)
                    else:
                        self.cfg["hotkeys"][act] = new
                        self.update_hotkey_ui()
                        self.save()
                        close()
                        return
                state["seen_clear"] = False
            d.after(30, poll)

        d.protocol("WM_DELETE_WINDOW", close)
        try:   # đặt hộp thoại giữa cửa sổ chính
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 3
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)
        d.after(200, poll)

    # ------------------------------------------------------------ Thiết lập lần đầu
    def wait_setup(self):
        """Chờ tới khi cửa sổ chính hiện (sau màn hình chào / khi mở từ khay) rồi mới mở thiết lập."""
        if self.quitting or getattr(self, "setup_win", None) is not None:
            return
        try:
            ready = self.win.winfo_viewable() and not getattr(self, "splashing", False)
        except (tk.TclError, AttributeError):
            ready = False
        if ready:
            self.run_setup()
        else:
            self.ov.after(400, self.wait_setup)

    def run_setup(self):
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        self.setup_win = d
        d.title(APP_NAME)
        d.resizable(False, False)
        d.transient(self.win)
        d.attributes("-topmost", True)
        running = {n.lower() for n, _ in list_running_apps()}
        app_set = {a.lower() for a in self.cfg["apps"]}
        st = {"step": 0, "shape": self.cfg["shape"] if self.cfg["shape"] in OWN_BY_ID else "EzDrop",
              "size": self.cfg["size"]}
        game_vars = [(tk.BooleanVar(value=any(e.lower() in running or e.lower() in app_set for e in exes)), title, exes)
                     for title, exes in ARPG_GAMES]
        all_var = tk.BooleanVar(value=self.cfg["all_apps"])

        outer = ctk.CTkFrame(d, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=(20, 18))
        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x")
        self.caps(top, "THIẾT LẬP NHANH", ACCENT).pack(side="left")
        step_lbl = ctk.CTkLabel(top, text="", font=self.F.m(11), text_color=MUTED)
        step_lbl.pack(side="right")
        bar = ctk.CTkFrame(outer, fg_color="transparent")
        bar.pack(fill="x", pady=(8, 14))
        dots = []
        for i in range(3):
            seg = ctk.CTkFrame(bar, height=4, corner_radius=2, fg_color=BORDER)
            seg.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 6, 0))
            dots.append(seg)
        body = ctk.CTkFrame(outer, fg_color="transparent", width=640, height=380)
        body.pack(fill="both", expand=True)
        body.pack_propagate(False)
        foot = ctk.CTkFrame(outer, fg_color="transparent")
        foot.pack(fill="x", pady=(14, 0))
        skip = ctk.CTkButton(foot, text=T("Bỏ qua"), width=90, height=40, fg_color="transparent",
                             hover_color="#1A1E29", text_color=TEXT2, font=self.F.b(13), command=lambda: finish(False))
        skip.pack(side="left")
        nxt = ctk.CTkButton(foot, text="", width=150, height=42, corner_radius=10, fg_color=ACCENT,
                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF", font=self.F.h(15),
                            command=lambda: go(1))
        nxt.pack(side="right")
        back = ctk.CTkButton(foot, text=T("Quay lại"), width=110, height=42, corner_radius=10, border_width=1,
                             border_color=BORDER, fg_color="transparent", hover_color="#1A1E29", text_color=TEXT,
                             font=self.F.b(13, strong=True), command=lambda: go(-1))

        def title(parent, t, sub):
            ctk.CTkLabel(parent, text=T(t), font=self.F.h(24), text_color=TEXT).pack(anchor="w")
            ctk.CTkLabel(parent, text=T(sub), font=self.F.b(13), text_color=TEXT2, wraplength=620,
                         justify="left").pack(anchor="w", pady=(2, 14))

        def page_games(f):
            title(f, "Bạn chơi game nào?", "EzCursor chỉ hiện con trỏ khi các game này đang mở. "
                                           "Có thể đổi sau ở tab Ứng dụng.")
            grid = ctk.CTkFrame(f, fg_color="transparent")
            grid.pack(fill="x")
            grid.grid_columnconfigure((0, 1), weight=1, uniform="g")
            for i, (var, name, exes) in enumerate(game_vars):
                cell = ctk.CTkFrame(grid, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=10,
                                    height=44)
                cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 5, 0 if i % 2 else 5),
                          pady=4)
                cb = ctk.CTkCheckBox(cell, text=name, variable=var, font=self.F.b(13, strong=True), text_color=TEXT,
                                     checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=1,
                                     fg_color=ACCENT, hover_color=ACCENT, border_color="#4A5266",
                                     checkmark_color="#FFFFFF")
                cb.pack(side="left", padx=12, pady=10)
                if any(e.lower() in running for e in exes):
                    ctk.CTkLabel(cell, text=T(" ĐANG CHẠY "), font=self.F.m(10), text_color=CYAN_TEXT,
                                 corner_radius=10, height=20, fg_color=mix(CARD, CYAN, 0.1)).pack(side="right", padx=10)
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=(14, 0))
            self.switch(row, all_var, lambda: None).pack(side="left")
            ctk.CTkLabel(row, text=T("  Áp dụng cho mọi ứng dụng (kể cả Desktop)"), font=self.F.b(13),
                         text_color=TEXT).pack(side="left")

        def page_cursor(f):
            title(f, "Chọn con trỏ", "Chọn con trỏ bạn thích. Bộ sưu tập còn bộ Bibata và chỗ thêm con trỏ "
                                     "của riêng bạn.")
            grid = ctk.CTkFrame(f, fg_color="transparent")
            grid.pack(fill="x")
            cols = 7
            for i in range(cols):
                grid.grid_columnconfigure(i, weight=1, uniform="c")
            tiles = {}
            name_lbl = ctk.CTkLabel(f, text="", font=self.F.b(14, strong=True), text_color=TEXT)

            def paint():
                name_lbl.configure(text=T(OWN_BY_ID[st["shape"]][1]))
                for sh, b in tiles.items():
                    on = sh == st["shape"]
                    b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                                hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                                border_color=ACCENT if on else BORDER)

            def pick(sh):
                st["shape"] = sh
                paint()

            n = 0
            for sh, label, _f, _h, _g in OWN_CURSORS:
                im = own_image(sh)
                if im is None:
                    continue
                b = ctk.CTkButton(grid, text="", width=10, height=78, corner_radius=12, border_width=1,
                                  image=ctk.CTkImage(im.resize((104, 104), Image.LANCZOS), size=(52, 52)),
                                  command=lambda sh=sh: pick(sh))
                b.grid(row=n // cols, column=n % cols, sticky="ew", padx=3, pady=3)
                tiles[sh] = b
                n += 1
            paint()
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=(16, 0))
            self.caps(row, "KÍCH THƯỚC").pack(side="left", padx=(0, 12))
            sizes = {T("Nhỏ"): 48, T("Vừa"): 64, T("Lớn"): 88}
            seg = ctk.CTkSegmentedButton(row, values=list(sizes), height=36, font=self.F.b(13, strong=True),
                                         fg_color=FIELD, unselected_color=FIELD, unselected_hover_color="#1A1E29",
                                         selected_color=mix(CARD, ACCENT, 0.35),
                                         selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT,
                                         command=lambda v: st.update(size=sizes[v]))
            seg.pack(side="left")
            name_lbl.pack(in_=row, side="right")
            name_lbl.lift()
            seg.set(min(sizes, key=lambda k: abs(sizes[k] - st["size"])))
            st["size"] = sizes[seg.get()]

        def page_done(f):
            title(f, "Sẵn sàng!", "Mở game là con trỏ mới sẽ hiện. Vài phím tắt nên nhớ:")
            games = [name for var, name, _ in game_vars if var.get()]
            card = self.card(f)
            card.pack(fill="x")
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=12)
            sh = st["shape"]
            line = ctk.CTkFrame(inner, fg_color="transparent")
            line.pack(fill="x", pady=(0, 8))
            if own_image(sh) is not None:
                ctk.CTkLabel(line, text="", image=ctk.CTkImage(own_image(sh).resize((80, 80), Image.LANCZOS),
                                                               size=(40, 40))).pack(side="left", padx=(0, 12))
            txt = ctk.CTkFrame(line, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(txt, text=T(OWN_BY_ID[sh][1]), font=self.F.b(15, strong=True), text_color=TEXT,
                         anchor="w").pack(anchor="w")
            where = T("Mọi ứng dụng") if all_var.get() else (", ".join(games) or T("(chưa chọn)"))
            ctk.CTkLabel(txt, text=T("Game") + ": " + where, font=self.F.b(12), text_color=TEXT2, anchor="w",
                         wraplength=520, justify="left").pack(anchor="w")
            hk = self.cfg["hotkeys"]
            for act, label in (("toggle", "Bật / tắt"), ("shape", "Đổi con trỏ (giữa các con trỏ yêu thích)"),
                               ("find", "Tìm con trỏ (hoặc lắc chuột)"), ("color", "Đổi màu")):
                r = ctk.CTkFrame(inner, fg_color="transparent")
                r.pack(fill="x", pady=2)
                ctk.CTkLabel(r, text=" + ".join(hotkey_parts(hk[act], act)), font=self.F.m(12), text_color=ACCENT,
                             width=150, anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=T(label), font=self.F.b(13), text_color=TEXT, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=T("EzCursor chạy ở khay hệ thống. Chuột phải vào icon để đổi nhanh con trỏ "
                                   "hoặc hồ sơ."), font=self.F.b(12), text_color=TEXT2, wraplength=620,
                         justify="left").pack(anchor="w", pady=(12, 0))

        pages = [page_games, page_cursor, page_done]

        def show():
            for w in body.winfo_children():
                w.destroy()
            f = ctk.CTkFrame(body, fg_color="transparent")
            f.pack(fill="both", expand=True)
            pages[st["step"]](f)
            i = st["step"]
            step_lbl.configure(text=T("Bước {i} / 3").format(i=i + 1))
            for k, seg in enumerate(dots):
                seg.configure(fg_color=ACCENT if k <= i else BORDER)
            nxt.configure(text=T("Bắt đầu") if i == 2 else T("Tiếp tục"))
            if i > 0:
                if not back.winfo_ismapped():
                    back.pack(side="right", padx=(0, 8))
            else:
                back.pack_forget()

        def go(delta):
            if st["step"] == 2 and delta > 0:
                finish(True)
                return
            st["step"] = max(0, min(2, st["step"] + delta))
            show()

        def finish(apply):
            if apply:
                apps = list(self.cfg["apps"])
                low = {a.lower() for a in apps}
                for var, _name, exes in game_vars:
                    for e in exes:
                        if var.get() and e.lower() not in low:
                            apps.append(e)
                            low.add(e.lower())
                        elif not var.get() and e.lower() in low:
                            apps = [a for a in apps if a.lower() != e.lower()]
                            low.discard(e.lower())
                self.cfg["apps"] = apps
                self.cfg["all_apps"] = bool(all_var.get())
                base = self.cfg.base
                base["shape"], base["size"] = st["shape"], st["size"]
                self.update_app_set()
                try:
                    self.all_var.set(self.cfg["all_apps"])
                    self.update_applied_label()
                except AttributeError:
                    pass
                self.refresh_apps()
                if self.cfg.target is base:
                    self.sync_style_widgets()
                self.refresh()
            self.cfg["setup_done"] = True
            self.save()
            self.setup_win = None
            try:
                d.destroy()
            except tk.TclError:
                pass
            self.show_tab("cursor")

        d.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        show()
        try:
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 3
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)
        d.after(250, lambda: d.grab_set() if d.winfo_exists() else None)

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
            CONFIG_PATH.write_text(json.dumps(self.cfg.base, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def status_info(self):
        if not self.enabled:
            return T("●  ĐANG TẮT"), MUTED, T("Con trỏ gốc đang được dùng.")
        if self.active:
            sub = T("Áp dụng cho mọi ứng dụng.") if self.cfg["all_apps"] else T("Trong game: ") + self.fg_exe
            pr = self.profile_for_exe(self.fg_exe)
            if pr:
                sub += "\n" + T("Hồ sơ: ") + pr["name"]
            return T("●  ĐANG HOẠT ĐỘNG"), GREEN, sub
        if self.shell_open:
            return T("●  TẠM DỪNG"), AMBER, T("Đang ở trên giao diện của Windows.")
        if self.fs_block:
            return T("●  FULLSCREEN"), AMBER, T("Game đang ở Fullscreen. Hãy chuyển sang Borderless hoặc Windowed.")
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

    def compose_cursor(self, outline=None, phase=0.0):
        """Ảnh con trỏ hoàn chỉnh dùng cho cả overlay lẫn xem trước: (ảnh, điểm click, màu quầng).
        outline: màu viền khi giữ chuột (None = không viền). phase: vị trí dải màu khi ombre chuyển động."""
        c = self.cfg
        s = self.eff_size()
        ombre = c["ombre"]
        oc = c["ombre_colors"]
        if own_image(c["shape"]) is not None:
            _, _, _, (hx, hy), glow_col = OWN_BY_ID[c["shape"]]
            if ombre:
                im = own_image(c["shape"]).resize((s, s), Image.LANCZOS)
            elif c["own_theme"] == "custom":
                im = own_image_colored(c["shape"], c["color"]).resize((s, s), Image.LANCZOS)
                glow_col = c["color"]
            else:
                im = own_image(c["shape"]).resize((s, s), Image.LANCZOS)
            hot = (round(hx * s / 256), round(hy * s / 256))
        elif c["shape"] == "Bibata" and BIBATA_DIR.exists():
            variant = self.bibata_variant()
            cols = bibata_colors("custom" if ombre else c["bibata_theme"], oc[0] if ombre else c["color"])
            im = bibata_image(BIBATA_DIR, variant, c["bibata_cursor"], cols).resize((s, s), Image.LANCZOS)
            hx, hy = BIBATA_META["hotspots"].get(f"{variant}/{c['bibata_cursor']}", [128, 128])
            hot = (round(hx * s / 256), round(hy * s / 256))
            glow_col = cols[0] if luminance(cols[0]) > 60 else cols[1]
        else:
            shape = c["shape"] if c["shape"] not in ("Bibata",) + tuple(OWN_BY_ID) else "Vòng tròn"
            src = self.src_img
            if src is not None and c["tint_image"] and not ombre:
                src = tint_image(src, c["color"])
            glow_col = oc[0] if ombre else self.preview_color()
            im, hot = render_shape(shape, glow_col, s, src, c["hotspot"], self.src_hot)
        if ombre:
            anim = c["ombre_anim"] and not self.animated_image()
            im = apply_ombre(im, ombre_tmap(im, hot), ombre_lut(oc, phase, anim))
            glow_col = oc[0]
        if c["hold_left"] or c["hold_right"]:      # mọi biến thể cùng kích thước để điểm click không lệch
            w = outline_width(s)
            im, hot = add_outline(im, hot, outline, w) if outline else pad_image(im, hot, w + 2)
        if c["glow"]:
            im, hot = add_glow(im, hot, glow_col)
        return im, hot, glow_col

    def eff_size(self):
        """Kích thước con trỏ thực tế (nhân tỉ lệ màn hình nếu bật)."""
        s = self.cfg["size"]
        return max(16, round(s * self.cur_scale)) if self.cfg["dpi_scale"] else s

    def animated_image(self):
        return (self.cfg["shape"] == "Ảnh tải lên" and self.src_frames is not None
                and len(self.src_frames) > 1 and bool(self.src_steps))

    def bibata_variant(self):
        return self.cfg["bibata_style"] + ("-right" if self.cfg["bibata_hand"] == "left" else "")

    def hold_colors(self):
        c = self.cfg
        out = {None: None}
        if c["hold_left"]:
            out["left"] = c["hold_left_color"]
        if c["hold_right"]:
            out["right"] = c["hold_right_color"]
        return out

    def render_key(self):
        c = self.cfg
        style = json.dumps({k: c[k] for k in STYLE_KEYS}, sort_keys=True, default=str)
        return (style, self.eff_size(), id(self.src_img), self.animated_image())

    def rebuild_overlay(self):
        cache = self.__dict__.setdefault("render_cache", collections.OrderedDict())
        key = self.render_key()
        self.render_key_now = key
        hit = cache.get(key)
        if hit is not None:
            cache.move_to_end(key)
            self.composed, self.variants = hit["composed"], hit["variants"]
        else:
            self.composed = self.compose_cursor()
            self.variants = {k: (self.composed if col is None else self.compose_cursor(col))
                             for k, col in self.hold_colors().items()}
            hit = cache[key] = {"composed": self.composed, "variants": self.variants}
            while len(cache) > 6:
                cache.popitem(last=False)
        im, self.ov_hot, _ = self.composed
        if getattr(self, "sys_cache", None) is not None:
            self.drop_system_cache()
            if self.active and self.system_mode():
                self.apply_system_cursor(force=True)
        self.cursor_frames = None
        self.frame_sets = None
        self.cursor_durations = None
        self.preview_photos = None
        self.show_img(self.variants.get(self.hold_state, self.composed)[0])
        if getattr(self, "_cf_job", None):
            self.ov.after_cancel(self._cf_job)
            self._cf_job = None
        if hit.get("frame_sets"):            # khung hình đã dựng trước đó: dùng lại ngay
            self.frame_sets = hit["frame_sets"]
            self.cursor_durations = hit["durations"]
            self.preview_photos = hit["photos"]
            self.ov_hot = hit["ov_hot"]
            self.cursor_frames = self.frame_sets.get(self.hold_state) or self.frame_sets[None]
            self.cf_idx, self.cf_next, self.pv_idx, self.pv_next = 0, 0.0, 0, 0.0
            self.show_img(self.cursor_frames[0])
            if self.active:
                self.move_overlay()
            return
        if self.animated_image():
            self._cf_job = self.ov.after(160, self.build_image_frames)
        elif self.cfg["cursor_sparkle"] or self.ombre_moving():
            self._cf_job = self.ov.after(160, self.build_cursor_frames)

    def remember_frames(self):
        hit = getattr(self, "render_cache", {}).get(getattr(self, "render_key_now", None))
        if hit is not None and self.frame_sets:
            hit.update(frame_sets=self.frame_sets, durations=self.cursor_durations,
                       photos=self.preview_photos, ov_hot=self.ov_hot)

    def ombre_moving(self):
        return self.cfg["ombre"] and self.cfg["ombre_anim"] and not self.animated_image()

    def build_image_frames(self):
        """Khung hình cho ảnh động (.ani / .gif), mỗi khung giữ đúng thời gian của file gốc."""
        self._cf_job = None
        if not self.animated_image():
            return
        keep = self.src_img
        sets, durs = {}, [ms for _, ms in self.src_steps]
        try:
            for key, col in self.hold_colors().items():
                cache, frames = {}, []
                for idx, _ms in self.src_steps:
                    if idx not in cache:
                        self.src_img = self.src_frames[idx]
                        cache[idx] = self.compose_cursor(col)[0]
                    frames.append(cache[idx])
                sets[key] = frames
        finally:
            self.src_img = keep
        frames = sets.get(None)
        if not frames or len({f.size for fs in sets.values() for f in fs}) != 1:
            return
        self.frame_sets = sets
        self.cursor_frames, self.cursor_durations = sets.get(self.hold_state, frames), durs
        self.cf_idx, self.cf_next = 0, 0.0
        self.show_img(self.cursor_frames[0])
        if self.active:
            self.move_overlay()
        self.pv_idx, self.pv_next = 0, 0.0
        photos = {}
        self.preview_photos = [photos.setdefault(id(fr), ImageTk.PhotoImage(fr, master=self.ov)) for fr in frames]
        self.remember_frames()

    def build_cursor_frames(self):
        """24 khung hình: ngôi sao nhấp nháy quanh con trỏ và/hoặc dải màu ombre chạy."""
        self._cf_job = None
        if not self.composed:
            return
        sets, pad = {}, 0
        moving = self.ombre_moving()
        cols = self.hold_colors()
        for key, comp in self.variants.items():
            ims = ([comp[0]] + [self.compose_cursor(cols.get(key), i / OMBRE_FRAMES)[0]
                                for i in range(1, OMBRE_FRAMES)]) if moving else None
            if self.cfg["cursor_sparkle"]:
                sets[key], pad = self.sparkle_frames(comp, ims)
            else:
                sets[key] = ims
        hot = self.composed[1]
        self.frame_sets = sets
        self.cursor_frames = sets.get(self.hold_state, sets[None])
        ms = OMBRE_SPEEDS[self.cfg["ombre_speed"]] if moving else 96
        self.cursor_durations = [ms] * len(self.cursor_frames)
        self.cf_idx, self.cf_next = 0, 0.0
        self.pv_idx, self.pv_next = 0, 0.0
        self.ov_hot = (hot[0] + pad, hot[1] + pad)
        self.show_img(self.cursor_frames[0])
        if self.active:
            self.move_overlay()
        self.preview_photos = [ImageTk.PhotoImage(fr, master=self.ov) for fr in sets[None]]
        self.remember_frames()

    def sparkle_frames(self, composed, ims=None):
        """24 khung hình có ngôi sao nhấp nháy quanh con trỏ; trả về (khung hình, phần lề thêm).
        ims: ảnh con trỏ riêng cho từng khung (ombre chuyển động)."""
        im, hot, gcol = composed
        s = self.eff_size()
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
            fr.alpha_composite(ims[i] if ims else im, (pad, pad))
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
        return frames, pad

    def set_hold(self, state):
        """Đổi ảnh con trỏ khi bắt đầu / thôi giữ chuột (ảnh đã vẽ sẵn nên rất nhẹ)."""
        if state == self.hold_state:
            return
        self.hold_state = state
        key = state if state in self.variants else None
        if self.active and self.system_mode():
            self.apply_system_cursor()
            return
        if self.frame_sets:
            self.cursor_frames = self.frame_sets.get(key) or self.frame_sets[None]
            self.show_img(self.cursor_frames[self.cf_idx % len(self.cursor_frames)])
        elif self.variants:
            self.show_img(self.variants.get(key, self.composed)[0])

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
        # con trỏ đang dùng màu gốc (bộ EzCursor / chủ đề Bibata có sẵn) thì không ô màu nào sáng
        uses_color = not ((c["shape"] in OWN_BY_ID and c["own_theme"] == "original")
                          or (c["shape"] == "Bibata" and c["bibata_theme"] != "custom") or c["ombre"])
        for col, b in self.swatch_buttons.items():
            on = uses_color and col.lower() == c["color"].lower()
            b.configure(border_width=3 if on else 0, border_color="#FFFFFF")
        custom = uses_color and c["color"].lower() not in {x.lower() for x, _ in SWATCHES}
        if custom:
            self.custom_btn.configure(fg_color=c["color"], hover_color=c["color"], border_width=3,
                                      border_color="#FFFFFF", image=None)
        else:
            self.custom_btn.configure(fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                      border_color="#4A5266",
                                      image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)))
        self.size_label.configure(text=f"{c['size']} px")
        self.update_ombre_ui()

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
        self.shell_open = shell_ui_open(self.cfg["keep_taskbar"])
        if self.shell_open:          # menu Start, Search, Alt+Tab... -> dùng con trỏ thật
            return False
        self.fg_exe = foreground_exe()
        if self.cfg["all_apps"]:
            want = True
        else:
            want = bool(self.app_set) and self.fg_exe.lower() in self.app_set
        if not want:
            self.fs_block = False
            return False
        if self.system_mode():
            self.fs_block = False
            return True
        now = time.perf_counter()
        if now - self.fs_checked > 0.5:          # kiểm tra Fullscreen 2 lần/giây là đủ
            self.fs_checked = now
            fs = fullscreen_exclusive()
            if fs != self.fs_block:
                self.fs_block = fs
                self.update_status()
                if fs:
                    self.warn_fullscreen()
        return not self.fs_block

    def warn_fullscreen(self):
        key = self.fg_exe.lower() or "*"
        if key in self.fs_warned:
            return
        self.fs_warned.add(key)
        own = key in self.cfg["sys_skip"]       # game tự đặt con trỏ riêng: Con trỏ thật cũng không giúp được
        try:
            self.icon.notify(T("Game này dùng con trỏ riêng và đang chạy Fullscreen nên EzCursor không thể hiện "
                               "con trỏ. Hãy chuyển game sang Borderless hoặc Windowed.") if own else
                             T("Game đang chạy Fullscreen nên EzCursor không vẽ được con trỏ. "
                               "Hãy chuyển game sang Borderless hoặc Windowed, hoặc bật chế độ "
                               "\"Con trỏ thật\" trong tab Tùy chọn.") if REAL_CURSOR_MODE else
                             T("Game đang chạy Fullscreen nên EzCursor không vẽ được con trỏ. "
                               "Hãy chuyển game sang Borderless hoặc Windowed trong phần cài đặt đồ họa."), APP_NAME)
        except Exception:
            pass

    def system_mode(self):
        """Đang dùng Con trỏ thật cho cửa sổ hiện tại (game tự đặt con trỏ riêng thì dùng Lớp phủ)."""
        return (REAL_CURSOR_MODE and self.cfg["cursor_mode"] == "system"
                and (getattr(self, "fg_exe", "") or "").lower() not in self.cfg["sys_skip"])

    def check_game_cursor(self, now):
        """Chế độ Con trỏ thật: game nào tự đặt / tự vẽ con trỏ thì ghi nhớ và chuyển game đó sang Lớp phủ."""
        if now - getattr(self, "gc_t", 0) < 0.5:
            return
        self.gc_t = now
        try:
            showing, h = current_cursor()
        except Exception:
            return
        foreign = (not showing) or (h is not None and not is_system_cursor(h))
        self.gc_hits = (getattr(self, "gc_hits", 0) + 1) if foreign else 0
        if self.gc_hits < 4:          # ~2 giây liên tục mới kết luận
            return
        self.gc_hits = 0
        exe = (self.fg_exe or "").lower()
        if not exe or exe in self.cfg["sys_skip"]:
            return
        self.cfg["sys_skip"] = self.cfg["sys_skip"] + [exe]
        log.info("Con trỏ thật: %s %s -> dùng Lớp phủ cho game này", exe,
                 "ẩn con trỏ Windows" if not showing else f"tự đặt con trỏ riêng ({h})")
        self.save()
        self.set_active(False)
        self.set_active(True)
        try:
            self.icon.notify(T("{g} dùng con trỏ riêng của game nên chế độ Con trỏ thật không đổi được. "
                               "EzCursor đã chuyển sang Lớp phủ cho game này.").format(g=Path(exe).stem), APP_NAME)
        except Exception:
            pass

    def set_active(self, on):
        if on == self.active:
            return
        self.active = on
        self.mode_on = self.system_mode() if on else None
        self.gc_hits = 0
        if not (on and self.system_mode()):      # tắt hoặc dùng Lớp phủ: luôn trả con trỏ Windows
            self.clear_system_cursor()
        if self.system_mode():
            show_real_cursor(True)
            self.ovl.show(False)
            if on:
                self.apply_system_cursor(force=True)
            else:
                self.clear_system_cursor()
        else:
            show_real_cursor(not (on and self.cfg["hide_real"]))
            if on:
                self.move_overlay()
            self.ovl.show(on)
        self.update_status()

    def apply_system_cursor(self, force=False):
        """Chế độ Con trỏ thật: đặt con trỏ Windows thành con trỏ EzCursor (theo trạng thái giữ chuột)."""
        key = self.hold_state if self.hold_state in self.variants else None
        if key == self.sys_key and not force:
            return
        comp = self.variants.get(key) or self.composed
        if comp is None:
            return
        try:
            hc = self.sys_cache.get(key)
            if hc is None:
                hc = make_hcursor(comp[0], comp[1])
                self.sys_cache[key] = hc
            ok, errs = set_system_cursors(hc)
            self.sys_key = key
            if not getattr(self, "sys_logged", False) or errs:
                self.sys_logged = True
                log.info("Con trỏ thật: đặt %d/%d con trỏ Windows, ảnh %s, cửa sổ đang mở: %s%s", ok,
                         len(SYS_CURSOR_IDS), comp[0].size, self.fg_exe or "?", (" | lỗi " + ", ".join(errs[:4])) if errs else "")
        except Exception:
            self.report_error("system cursor", once=True)

    def clear_system_cursor(self):
        restore_system_cursors()
        self.sys_key = "?"

    def drop_system_cache(self):
        for hc in self.sys_cache.values():
            try:
                user32.DestroyCursor(hc)
            except Exception:
                pass
        self.sys_cache = {}
        self.sys_key = "?"

    def set_cursor_mode(self, mode):
        if mode == self.cfg["cursor_mode"]:
            return
        self.set_active(False)          # tắt theo chế độ cũ; vòng lặp sẽ bật lại theo chế độ mới
        self.clear_system_cursor()
        self.cfg["cursor_mode"] = mode
        if mode == "system":
            self.cfg["sys_skip"] = []
        self.update_mode_ui()
        self.save()
        if mode == "system":          # cho xem thử ngay 3 giây trên màn hình hiện tại
            self.apply_system_cursor(force=True)
            self.ov.after(3000, lambda: None if (self.active and self.system_mode()) else self.clear_system_cursor())

    # ------------------------------------------------------------ Danh sách ứng dụng
    def refresh_apps(self):
        _name_cache.clear()
        running = list_running_apps()
        running_names = {n.lower() for n, _ in running}
        # (khóa, tiêu đề, dòng phụ, các file chạy, trạng thái)
        items = [(n, t, n, [n], "run") for n, t in running]
        preset_of = {exe.lower(): (title, exes) for title, exes in ARPG_GAMES for exe in exes}
        shown_presets = set()
        for n in self.cfg["apps"]:
            if n.lower() in running_names:
                continue
            pre = preset_of.get(n.lower())
            if pre and not any(e.lower() in running_names for e in pre[1]):
                if pre[0] not in shown_presets:
                    shown_presets.add(pre[0])
                    items.append(("preset:" + pre[0], pre[0], ", ".join(pre[1]), pre[1], "off"))
            else:
                items.append((n, T("(đang không chạy)"), n, [n], "off"))
        suggest = [("preset:" + title, title, ", ".join(exes), exes, "hint") for title, exes in ARPG_GAMES
                   if title not in shown_presets and not any(e.lower() in running_names for e in exes)]
        old = {k: v[0].get() for k, v in self.app_vars.items()}
        for w in self.app_list.winfo_children():
            w.destroy()
        self.app_vars = {}
        for i, (key, title, sub, exes, state) in enumerate(items + suggest):
            if i == len(items) and suggest:
                self.caps(self.app_list, "GỢI Ý: GAME ARPG PHỔ BIẾN").pack(anchor="w", padx=12, pady=(12, 4))
            checked = old.get(key, any(e.lower() in self.app_set for e in exes))
            var = tk.BooleanVar(value=checked)
            self.app_vars[key] = (var, exes)
            pname = title if key.startswith("preset:") else Path(exes[0]).stem
            self.add_app_row(sub, title, state, var, exes, pname)

    def add_app_row(self, name, title, running, var, exes=(), pname=""):
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
        sub = name if len(name) <= 70 else name[:67] + "..."
        l2 = ctk.CTkLabel(txt, text=sub, font=self.F.m(12), text_color=MUTED, height=16, anchor="w")
        l2.pack(anchor="w")
        badge_txt, badge_col, badge_bg = {
            "run": (T(" ĐANG CHẠY "), CYAN_TEXT, mix(CARD, CYAN, 0.1)),
            "hint": (T(" GỢI Ý "), GREEN, mix(CARD, GREEN, 0.1)),
        }.get(running, (T(" KHÔNG CHẠY "), MUTED, "#181C26"))
        badge = ctk.CTkLabel(row, text=badge_txt, font=self.F.m(10), text_color=badge_col, corner_radius=11,
                             height=22, fg_color=badge_bg)
        badge.pack(side="right", padx=12, before=txt)
        has = any(self.profile_for_exe(e) for e in exes)
        prof = ctk.CTkButton(row, text=T("✓ Hồ sơ riêng") if has else T("+ Hồ sơ riêng"), width=10, height=26,
                             corner_radius=8, font=self.F.b(12, strong=has), border_width=1,
                             border_color=ACCENT if has else BORDER,
                             fg_color=mix(CARD, ACCENT, 0.18) if has else "transparent",
                             hover_color=mix(CARD, ACCENT, 0.28), text_color="#FFFFFF" if has else TEXT2,
                             command=lambda: self.open_profile(list(exes), pname or title))
        if exes:
            prof.pack(side="right", before=txt)

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
        apps = []
        for var, exes in self.app_vars.values():
            if var.get():
                apps += [e for e in exes if e.lower() not in {a.lower() for a in apps}]
        self.cfg["apps"] = apps
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
        favs = [f for f in self.cfg["favorites"] if self.fav_valid(f)]
        if favs:
            cur = self.current_fav_id()
            i = favs.index(cur) if cur in favs else -1
            self.use_fav(favs[(i + 1) % len(favs)])
            return
        options = [x for x in SHAPES if x != "Ảnh tải lên" or self.src_img is not None]
        cur = self.cfg["shape"]
        i = options.index(cur) if cur in options else -1
        self.set_shape(options[(i + 1) % len(options)])

    def set_color(self, color):
        if color.lower() == TRANSPARENT:
            color = "#020202"
        self.cfg["color"] = color
        self.cfg["ombre"] = False
        if self.cfg["shape"] == "Bibata":
            self.cfg["bibata_theme"] = "custom"
        elif self.cfg["shape"] in OWN_BY_ID:
            self.cfg["own_theme"] = "custom"
        self.refresh()

    def pick_color(self):
        res = colorchooser.askcolor(color=self.cfg["color"], parent=self.win, title=T("Chọn màu"))
        if res and res[1]:
            self.set_color(res[1])

    # ------------------------------------------------------------ Màu ombre
    def build_ombre_box(self, parent):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=14, pady=(0, 12))
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x")
        self.caps(head, "MÀU OMBRE").pack(side="left")
        self.ombre_name = ctk.CTkLabel(head, text="", font=self.F.b(12), text_color=TEXT2)
        self.ombre_name.pack(side="left", padx=(8, 0))
        self.ombre_var = tk.BooleanVar(value=self.cfg["ombre"])
        self.switch(head, self.ombre_var, lambda: self.set_ombre(bool(self.ombre_var.get()))).pack(side="right")
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", pady=(8, 8))
        self.ombre_btns = {}
        self.ombre_imgs = {}
        for key, name, cols in OMBRE_PRESETS:
            self.ombre_imgs[key] = {on: ctk.CTkImage(ombre_dot(cols, on), size=(30, 30)) for on in (False, True)}
            b = ctk.CTkLabel(row, text="", width=30, height=30, image=self.ombre_imgs[key][False], cursor="hand2")
            b.bind("<Button-1>", lambda e, cl=cols: self.set_ombre(True, cl))
            b.pack(side="left", padx=(0, 5))
            self.ombre_btns[key] = b
        self.ombre_plus = ctk.CTkImage(ombre_dot(None, False), size=(30, 30))
        self.ombre_custom = ctk.CTkLabel(row, text="", width=30, height=30, image=self.ombre_plus, cursor="hand2")
        self.ombre_custom.bind("<Button-1>", lambda e: self.pick_ombre())
        self.ombre_custom.pack(side="left")
        row2 = ctk.CTkFrame(box, fg_color="transparent")
        row2.pack(fill="x")
        self.ombre_anim_var = tk.BooleanVar(value=self.cfg["ombre_anim"])
        self.switch(row2, self.ombre_anim_var, self.set_ombre_anim).pack(side="left")
        ctk.CTkLabel(row2, text=T("  Chuyển động"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.ombre_speed_map = {T("Chậm"): "slow", T("Vừa"): "mid", T("Nhanh"): "fast"}
        self.ombre_speed_seg = ctk.CTkSegmentedButton(
            row2, values=list(self.ombre_speed_map), height=30, font=self.F.b(12, strong=True), fg_color=FIELD,
            unselected_color=FIELD, unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
            selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT,
            command=lambda v: self.set_ombre_speed(self.ombre_speed_map[v]))
        self.ombre_speed_seg.pack(side="right")

    def update_ombre_ui(self):
        c = self.cfg
        if not hasattr(self, "ombre_btns"):
            return
        try:
            self.ombre_var.set(c["ombre"])
            self.ombre_anim_var.set(c["ombre_anim"])
            self.ombre_speed_seg.set({v: k for k, v in self.ombre_speed_map.items()}[c["ombre_speed"]])
            cur = [x.lower() for x in c["ombre_colors"]]
            name = ""
            for key, pname, cols in OMBRE_PRESETS:
                on = c["ombre"] and [x.lower() for x in cols] == cur
                self.ombre_btns[key].configure(image=self.ombre_imgs[key][on])
                if [x.lower() for x in cols] == cur:
                    name = T(pname)
            custom = not name
            self.ombre_custom.configure(image=ctk.CTkImage(ombre_dot(c["ombre_colors"], c["ombre"]), size=(30, 30))
                                        if custom else self.ombre_plus)
            self.ombre_name.configure(text=("· " + (name or T("Tự chọn"))) if c["ombre"] else "")
            state = "normal" if c["ombre"] else "disabled"
            self.ombre_speed_seg.configure(state=state if c["ombre_anim"] else "disabled")
        except (tk.TclError, AttributeError, KeyError):
            pass

    def set_ombre(self, on, colors=None):
        c = self.cfg
        c["ombre"] = on
        if colors:
            c["ombre_colors"] = list(colors)
        self.refresh()

    def set_ombre_anim(self):
        self.cfg["ombre_anim"] = bool(self.ombre_anim_var.get())
        if self.cfg["ombre_anim"]:
            self.cfg["ombre"] = True
        self.refresh()

    def set_ombre_speed(self, speed):
        self.cfg["ombre_speed"] = speed
        self.refresh()

    def lib_ombre(self, view):
        """Chip "Ombre" trong Bộ sưu tập: dùng dải màu cho nhóm con trỏ đang xem."""
        if view == "ez" and self.cfg["shape"] not in OWN_BY_ID:
            self.cfg["shape"] = "EzDrop"
        elif view == "bibata":
            self.cfg["shape"] = "Bibata"
        self.set_ombre(True)

    def pick_ombre(self):
        """Hộp thoại tự chọn 2 hoặc 3 màu ombre."""
        cols = list(self.cfg["ombre_colors"][:3])
        while len(cols) < 3:
            cols.append(cols[-1])
        three = tk.BooleanVar(value=len(self.cfg["ombre_colors"]) >= 3)
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        d.title(T("Tự chọn màu ombre"))
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.transient(self.win)
        frm = ctk.CTkFrame(d, fg_color="transparent")
        frm.pack(fill="both", padx=22, pady=18)
        ctk.CTkLabel(frm, text=T("Tự chọn màu ombre"), font=self.F.h(18), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(frm, text=T("Màu 1 ở mũi con trỏ, màu cuối ở đuôi."), font=self.F.b(12),
                     text_color=TEXT2).pack(anchor="w", pady=(2, 12))
        row = ctk.CTkFrame(frm, fg_color="transparent")
        row.pack(anchor="w")
        bar = ctk.CTkLabel(frm, text="")
        btns = []

        def used():
            return cols[:3] if three.get() else cols[:2]

        def paint():
            for i, b in enumerate(btns):
                b.configure(fg_color=cols[i], hover_color=cols[i], state="normal" if i < 2 or three.get() else "disabled")
            btns[2].configure(fg_color=cols[2] if three.get() else FIELD)
            bar.configure(image=ctk.CTkImage(ombre_swatch(used(), 30, round_=False), size=(240, 30)))

        def pick(i):
            res = colorchooser.askcolor(color=cols[i], parent=d, title=T("Chọn màu"))
            if res and res[1]:
                cols[i] = res[1].upper()
                paint()

        for i in range(3):
            b = ctk.CTkButton(row, text=str(i + 1), width=44, height=44, corner_radius=22, border_width=2,
                              border_color="#FFFFFF", text_color="#0B0D12", font=self.F.b(13, strong=True),
                              command=lambda i=i: pick(i))
            b.pack(side="left", padx=(0, 10))
            btns.append(b)
        ctk.CTkCheckBox(frm, text=T("Dùng 3 màu"), variable=three, command=paint, font=self.F.b(13),
                        text_color=TEXT, checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=1,
                        fg_color=ACCENT, hover_color=ACCENT, border_color="#4A5266",
                        checkmark_color="#FFFFFF").pack(anchor="w", pady=(12, 10))
        bar.pack(anchor="w")
        foot = ctk.CTkFrame(frm, fg_color="transparent")
        foot.pack(fill="x", pady=(16, 0))

        def ok():
            self.set_ombre(True, used())
            d.destroy()

        ctk.CTkButton(foot, text=T("Dùng dải màu này"), command=ok, height=40, corner_radius=10, fg_color=ACCENT,
                      hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF",
                      font=self.F.b(13, strong=True)).pack(side="right")
        ctk.CTkButton(foot, text=T("Hủy"), command=d.destroy, width=80, height=40, corner_radius=10,
                      fg_color="transparent", hover_color="#1A1E29", text_color=TEXT2,
                      font=self.F.b(13)).pack(side="right", padx=(0, 8))
        paint()
        try:
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 3
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)

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

    def set_dpi_scale(self):
        self.cfg["dpi_scale"] = bool(self.dpi_var.get())
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        self.cur_scale = monitor_scale(pt.x, pt.y)
        self.refresh()

    def check_monitor(self):
        """Đổi kích thước con trỏ khi chuột sang màn hình có tỉ lệ khác (nếu bật)."""
        if not self.cfg["dpi_scale"]:
            return
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        sc = monitor_scale(pt.x, pt.y)
        if abs(sc - self.cur_scale) > 0.01:
            self.cur_scale = sc
            self.rebuild_overlay()
            self.update_preview()
            if self.active:
                self.move_overlay()

    def set_hotspot(self, h):
        self.cfg["hotspot"] = h
        self.refresh()

    def update_mode_ui(self):
        try:
            sysm = self.system_mode()
            self.mode_seg.set({v: k for k, v in self.mode_map.items()}[self.cfg["cursor_mode"]])
            self.mode_sub.configure(text=T("Không độ trễ, chạy cả Fullscreen. Không có lấp lánh, ombre chuyển động.")
                                    if sysm else T("Đủ hiệu ứng. Game cần chạy Borderless hoặc Windowed."))
        except (AttributeError, tk.TclError):
            pass

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
            filetypes=[(T("Ảnh hoặc con trỏ"), "*.png *.gif *.webp *.ico *.cur *.ani *.bmp *.jpg *.jpeg"),
                       (T("Con trỏ Windows"), "*.cur *.ani"), (T("Tất cả"), "*.*")])
        if not path:
            return
        try:
            load_cursor_file(path)                    # thử đọc trước khi lưu
        except Exception as e:
            messagebox.showerror(T("Lỗi"), T("Không mở được ảnh:") + f"\n{e}", parent=self.win)
            return
        try:
            MY_DIR.mkdir(parents=True, exist_ok=True)
            dest = unique_my_path(Path(path).name)
            shutil.copyfile(path, dest)
        except Exception as e:
            messagebox.showerror(T("Lỗi"), T("Không sao chép được ảnh:") + f"\n{e}", parent=self.win)
            return
        self.use_my_cursor(dest)
        self.rebuild_mine_tiles()

    def use_my_cursor(self, path):
        """Dùng một con trỏ trong "Con trỏ của bạn"."""
        path = Path(path)
        if not self.load_image(str(path)):
            return
        self.cfg["image"] = str(path)
        self.img_label.configure(text=path.name)
        if self.src_hot is not None:
            self.cfg["hotspot"] = "Theo file"
        elif self.cfg["hotspot"] == "Theo file":
            self.cfg["hotspot"] = HOTSPOTS[0]
        self.hot_seg.set(T(self.cfg["hotspot"]))
        self.set_shape("Ảnh tải lên")

    def delete_my_cursor(self):
        img = self.cfg["image"]
        if not (self.cfg["shape"] == "Ảnh tải lên" and img and Path(img).parent == MY_DIR):
            return
        if not messagebox.askyesno(APP_NAME, T("Xóa con trỏ \"{n}\" khỏi bộ sưu tập?").format(n=Path(img).stem),
                                   parent=self.win):
            return
        try:
            Path(img).unlink()
        except OSError:
            pass
        self.cfg["favorites"] = [f for f in self.cfg["favorites"] if f != "my:" + Path(img).name]
        self.cfg["made_cursors"] = {k: v for k, v in self.cfg["made_cursors"].items() if k != Path(img).name}
        for st in [self.cfg.base] + [pr["style"] for pr in self.cfg["profiles"]]:
            if st.get("image") == img:
                st["image"] = ""
                if st.get("shape") == "Ảnh tải lên":
                    st["shape"] = "EzDrop"
        self.img_cache.clear()
        self.clear_image()
        self.img_label.configure(text=T("(chưa có ảnh)"))
        self.rebuild_mine_tiles()
        self.refresh()

    def profile_name_of_target(self):
        for pr in self.cfg["profiles"]:
            if pr["style"] is self.cfg.target:
                return pr["name"]
        return "game"

    def clear_image(self):
        self.src_img = self.src_frames = self.src_steps = self.src_hot = None

    def load_image(self, path, silent=False):
        try:
            key = (path, os.path.getmtime(path))
            if key not in self.img_cache:
                if len(self.img_cache) > 8:
                    self.img_cache.clear()
                self.img_cache[key] = load_cursor_file(path)
            frames, self.src_hot, steps = self.img_cache[key]
            self.src_img = frames[0]
            self.src_frames, self.src_steps = (frames, steps) if steps and len(frames) > 1 else (None, None)
        except Exception as e:
            self.src_img = self.src_frames = self.src_steps = self.src_hot = None
            if not silent:
                messagebox.showerror(T("Lỗi"), T("Không mở được ảnh:") + f"\n{e}", parent=self.win)
            return False
        return True

    def show_img(self, im):
        """Đặt ảnh con trỏ; trong lúc hiệu ứng tìm con trỏ chạy thì chỉ ghi nhớ, vẽ lại khi xong."""
        self.shown_img = im
        if self.find_t0 is None:
            self.ovl.set_image(im)

    def record_perf(self, now):
        """Đo nhịp vòng lặp khi con trỏ đang hiện; ghi log một lần sau ~20 giây."""
        pf = self.__dict__.setdefault("perf", {"t0": None, "n": 0, "gap": 0.0, "last": 0.0, "done": False})
        if pf["done"]:
            return
        if pf["t0"] is None:
            pf.update(t0=now, last=now)
            return
        if pf["last"] is None:          # vừa quay lại game sau khi tạm tắt
            pf["last"] = now
            return
        pf["n"] += 1
        pf["gap"] = max(pf["gap"], now - pf["last"])
        pf["last"] = now
        if now - pf["t0"] >= 20:
            pf["done"] = True
            log.info("Độ trễ lớp phủ: bám chuột mỗi %.1f ms, chậm nhất %.0f ms, đoán trước: %s, màn hình %d Hz",
                     (now - pf["t0"]) * 1000 / max(1, pf["n"]), pf["gap"] * 1000,
                     "bật" if self.cfg["predict"] else "tắt", self.refresh_hz())

    def refresh_hz(self):
        if not getattr(self, "_hz", None):
            try:
                hdc = user32.GetDC(None)
                hz = ctypes.windll.gdi32.GetDeviceCaps(hdc, 116)          # VREFRESH
                user32.ReleaseDC(None, hdc)
                self._hz = hz if isinstance(hz, int) and 30 <= hz <= 500 else 60
            except Exception:
                self._hz = 60
        return self._hz

    def predicted(self, x, y):
        """Đoán vị trí chuột sau ~nửa khung hình theo tốc độ hiện tại (đổi hướng / chậm thì không đoán)."""
        now = time.perf_counter()
        hist = self.__dict__.setdefault("mhist", collections.deque(maxlen=16))
        hist.append((now, x, y))
        old = next((h for h in hist if now - h[0] <= 0.012), None)
        if old is None or now - old[0] < 0.003:
            return x, y
        dt = now - old[0]
        vx, vy = (x - old[1]) / dt, (y - old[2]) / dt
        pv = getattr(self, "prev_v", (0.0, 0.0))
        self.prev_v = (vx, vy)
        if vx * pv[0] + vy * pv[1] < 0 or (vx * vx + vy * vy) < 200 ** 2:     # đổi hướng hoặc rê chậm
            return x, y
        lead = 0.5 / self.refresh_hz()
        dx, dy = vx * lead, vy * lead
        m = math.hypot(dx, dy)
        if m > 40:
            dx, dy = dx * 40 / m, dy * 40 / m
        return int(round(x + dx)), int(round(y + dy))

    def follow_loop(self):
        """Vòng bám chuột riêng, rất nhẹ (~1 ms) – chỉ dời cửa sổ con trỏ khi đang hiện bằng lớp phủ."""
        if self.quitting:
            return
        busy = False
        try:
            if self.active and self.find_t0 is None and not self.system_mode():
                busy = True
                self.move_overlay(only_if_moved=True)
                self.record_perf(time.perf_counter())
        except Exception:
            self.report_error("follow", once=True)
        try:
            self.ov.after(1 if busy else 50, self.follow_loop)
        except tk.TclError:
            pass

    def move_overlay(self, only_if_moved=False):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if self.cfg["predict"] and self.find_hot is None:
            pt.x, pt.y = self.predicted(pt.x, pt.y)
        hot = self.find_hot or self.ov_hot
        key = (pt.x, pt.y, hot)
        if only_if_moved and key == self.last_move:
            return
        self.last_move = key
        self.ovl.move(int(pt.x - hot[0]), int(pt.y - hot[1]))

    # ------------------------------------------------------------ Tìm con trỏ nhanh
    FIND_TIME = 0.9

    def start_find(self):
        """Phóng to con trỏ + tỏa vòng sáng ~1 giây để tìm thấy con trỏ ngay."""
        if not self.enabled:
            return
        self.find_t0 = time.perf_counter()
        self.find_ring_only = not self.active or self.system_mode()
        self.find_cool = self.find_t0 + 1.5

    def find_frame(self, now):
        p = (now - self.find_t0) / self.FIND_TIME
        if p >= 1:
            self.end_find()
            return
        base = None if self.find_ring_only else self.shown_img
        hot = self.ov_hot
        size = self.eff_size()
        bw = max(base.size) if base is not None else size
        bump = math.sin(math.pi * min(1.0, p / 0.9)) ** 0.7
        k = 1 + 1.5 * bump
        C = int(bw * 3.6) + 8
        C -= C % 2
        cv = Image.new("RGBA", (C, C), (0, 0, 0, 0))
        d = ImageDraw.Draw(cv)
        col = _rgb(self.glow_color())
        lw = max(4, size // 10)
        for delay in (0.0, 0.28):
            q = (p - delay) / (1 - delay)
            if 0 <= q <= 1:
                r = size * 0.45 + q * (C / 2 - lw - size * 0.45)
                a = int(255 * (1 - q) ** 1.3)
                d.ellipse([C / 2 - r, C / 2 - r, C / 2 + r, C / 2 + r], outline=col + (a,), width=lw)
                d.ellipse([C / 2 - r - lw, C / 2 - r - lw, C / 2 + r + lw, C / 2 + r + lw],
                          outline=(255, 255, 255, a // 3), width=max(1, lw // 2))
        if base is not None:
            sw, sh = max(1, round(base.width * k)), max(1, round(base.height * k))
            big = base.resize((sw, sh), Image.BILINEAR)
            ox, oy = round(C / 2 - hot[0] * k), round(C / 2 - hot[1] * k)
            cv.alpha_composite(big, (max(0, ox), max(0, oy)),
                               (max(0, -ox), max(0, -oy)))
        self.ovl.set_image(cv)
        self.find_hot = (C // 2, C // 2)
        if not self.ovl.visible:
            self.ovl.show(True)
        self.move_overlay()

    def end_find(self):
        self.find_t0 = None
        self.find_hot = None
        if self.shown_img is not None:
            self.ovl.set_image(self.shown_img)
        if self.find_ring_only and (not self.active or self.system_mode()):
            self.ovl.show(False)
        self.find_ring_only = False
        self.move_overlay()

    def check_shake(self, now):
        """Lắc chuột qua lại nhanh (≥4 lần đổi hướng trong 0,8 giây) thì tìm con trỏ."""
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if self.sh_last_x is None:
            self.sh_last_x = pt.x
            return
        dx = pt.x - self.sh_last_x
        self.sh_last_x = pt.x
        if dx:
            sign = 1 if dx > 0 else -1
            if sign == self.sh_dir:
                self.sh_seg += abs(dx)
            else:
                if self.sh_seg >= 60 * self.cur_scale:
                    self.sh_rev.append(now)
                self.sh_dir, self.sh_seg = sign, abs(dx)
        self.sh_rev = [t for t in self.sh_rev if now - t < 0.8]
        if len(self.sh_rev) >= 4 and now > self.find_cool and self.find_t0 is None:
            self.sh_rev = []
            self.start_find()

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
        if getattr(self, "ui_dirty", False):
            self.ui_dirty = False
            try:
                self.sync_style_widgets()
                self.update_controls()
                self.update_library()
                self.update_fx_ui()
                self.update_preview()
            except Exception:
                self.report_error("ui refresh", once=True)
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
        for f in list(APP_DIR.glob("custom*.*")) + list(my_cursor_files()):
            try:
                f.unlink()
            except OSError:
                pass
        self.cfg = ProfileCfg(default_cfg())
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
        self.profile_menus = []
        self.build_ui()
        self.refresh_apps()
        self.refresh()
        self.show_tab(tab)
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def set_predict(self):
        self.cfg["predict"] = bool(self.predict_var.get())
        self.save()

    def set_keep_taskbar(self):
        self.cfg["keep_taskbar"] = bool(self.taskbar_var.get())
        self.save()

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
            ms = time.perf_counter() * 1000
            if self.tab == "cursor" and self.preview_photos and self.cursor_durations and ms >= self.pv_next:
                self.pv_idx = (self.pv_idx + 1) % len(self.preview_photos)
                self.pv_next = ms + self.cursor_durations[self.pv_idx % len(self.cursor_durations)]
                self.pcv.itemconfig(self.pimg_id, image=self.preview_photos[self.pv_idx])
            if f % 24 == 0:
                self.update_status(blink=(f // 24) % 2 == 1 and self.active)
        self.ov.after(33, self.anim)

    def check_hotkeys(self):
        if self.capturing:
            return True
        now = set()
        down = mods_down()
        if down & {"ctrl", "alt"}:
            hk = self.cfg["hotkeys"]
            for act in ("toggle", "shape", "quit", "find"):
                if set(hk[act]["mods"]) == down and key_down(hk[act]["vk"]):
                    now.add(act)
            if set(hk["color"]["mods"]) == down:
                for i in range(5):
                    if key_down(0x31 + i):
                        now.add(f"c{i}")
        elif self.prev_keys == {"*"}:
            self.prev_keys = set()
        if self.prev_keys == {"*"}:
            return True
        for act in now - self.prev_keys:
            if act.startswith("c"):
                self.set_color(PRESET_COLORS[int(act[1])])
            elif act == "shape":
                self.next_shape()
            elif act == "toggle":
                self.toggle()
            elif act == "find":
                self.start_find()
            elif act == "quit":
                self.quit()
                return False
        self.prev_keys = now
        return True

    def process_queue(self):
        while not self.q.empty():
            cmd = self.q.get()
            if isinstance(cmd, tuple):
                if cmd[0].startswith("tray_"):
                    self.handle_tray(*cmd)
                elif cmd[0].startswith("cat_"):
                    self.handle_catalog(*cmd)
                else:
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
        """Vòng lặp chính (~4 ms). Lỗi ở đây được ghi log và vòng lặp vẫn chạy tiếp."""
        if self.quitting:
            return
        try:
            if not self.tick_body():
                return
        except Exception:
            if self.quitting:
                return
            self.report_error("tick")
        try:
            self.ov.after(4, self.tick)
        except tk.TclError:
            pass

    def tick_body(self):
        now = time.perf_counter()
        if not self.process_queue():
            return False
        if now - self.t_keys >= 0.015:              # phím tắt: ~65 lần/giây là đủ
            self.t_keys = now
            if not self.check_hotkeys():
                return False
        if now - self.t_flags >= 0.1:                # tín hiệu từ bộ cài, đổi màn hình: 10 lần/giây
            self.t_flags = now
            self.check_monitor()
            self.sync_tray()
            for flag, action in ((SHOW_FLAG, self.show_window), (QUIT_FLAG, self.quit)):
                if flag.exists():
                    try:
                        flag.unlink()
                    except OSError:
                        pass
                    action()
                    if flag is QUIT_FLAG:
                        return False
        if now - self.t_active >= 0.05:              # game đang mở, menu Start, Fullscreen: 20 lần/giây
            self.t_active = now
            was_shell = self.shell_open
            want = self.compute_active() and not self.safe_mode
            if want:      # đổi sang hồ sơ của game trước khi hiện con trỏ
                pr = self.profile_for_exe(self.fg_exe)
                self.tray_pr = pr
                self.use_style(self.style_of(pr))
            self.set_active(want)
            if self.active and self.system_mode() != self.mode_on:     # đổi sang game dùng chế độ khác
                self.set_active(False)
                self.set_active(True)
            if self.active and self.mode_on:
                self.check_game_cursor(now)
            if not self.active:
                self.use_style(self.style_of(self.edit_profile))
            if was_shell != self.shell_open:
                self.update_status()
        if self.active and self.cfg["find_shake"]:
            self.check_shake(now)
        if self.active:
            l, r = mouse_buttons()
            c = self.cfg
            self.set_hold("right" if r and c["hold_right"] else "left" if l and c["hold_left"] else None)
            if not self.system_mode():
                self.move_overlay(only_if_moved=True)
                if now - getattr(self, "t_top", 0) >= 0.5:     # giữ cửa sổ con trỏ luôn trên cùng
                    self.t_top = now
                    self.ovl.raise_top()
        elif self.hold_state is not None:
            self.set_hold(None)
        if not self.active and getattr(self, "perf", None):
            self.perf["last"] = None
        return True

    # ------------------------------------------------------------ Lỗi & nhật ký
    def report_error(self, where, once=False, exc_info=None):
        """Ghi lỗi vào log; lỗi lặp lại liên tục ở vòng lặp chính thì tạm tắt con trỏ cho an toàn."""
        exc_info = exc_info or sys.exc_info()
        exc = exc_info[1]
        key = (where, type(exc).__name__, str(exc)[:200])
        if once and key in self.logged_errors:
            return
        if len(self.logged_errors) < 200:
            self.logged_errors.add(key)
            log.error("Lỗi ở %s:\n%s", where, "".join(traceback.format_exception(*exc_info)))
        if once:
            return
        now = time.perf_counter()
        self.err_times = [t for t in self.err_times if now - t < 10] + [now]
        if len(self.err_times) >= 15 and not self.safe_mode:
            self.enter_safe_mode()

    def on_tk_error(self, exc_type, exc, tb):
        if self.quitting:
            return
        self.report_error("giao diện", exc_info=(exc_type, exc, tb))

    def enter_safe_mode(self):
        self.safe_mode = True
        log.critical("Lỗi lặp lại liên tục, tạm tắt con trỏ EzCursor.")
        emergency_cursor()
        self.sys_key = "?"
        try:
            self.active = False
            self.ovl.show(False)
            self.fxw.show(False)
        except Exception:
            pass
        try:
            self.icon.notify(T("EzCursor gặp lỗi liên tục nên đã tạm tắt con trỏ để bạn dùng chuột bình thường. "
                               "Hãy mở lại EzCursor; chi tiết lỗi nằm trong file ezcursor.log."), APP_NAME)
        except Exception:
            pass

    def open_log_folder(self):
        try:
            os.startfile(str(APP_DIR))
        except Exception as e:
            messagebox.showerror(T("Lỗi"), str(e), parent=self.win)

    def quit(self):
        self.quitting = True
        log.info("Thoát EzCursor.")
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
    setup_logging()
    app = App(start_in_tray="--tray" in sys.argv)
    app.ov.mainloop()


def setup_logging():
    """Nhật ký lỗi tại %APPDATA%\\EzCursor\\ezcursor.log (tự xoay vòng, tối đa ~1 MB)."""
    try:
        h = logging.handlers.RotatingFileHandler(APP_DIR / "ezcursor.log", maxBytes=512 * 1024, backupCount=1,
                                                 encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        w, hgt = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        log.info("Khởi động EzCursor %s | %s | Python %s | %s | màn hình %sx%s",
                 APP_VERSION, platform.platform(), platform.python_version(),
                 "bản cài" if getattr(sys, "frozen", False) else "mã nguồn", w, hgt)
    except Exception:
        pass


if __name__ == "__main__":
    main()

"""Dọn dẹp khi thoát, bắt lỗi chưa xử lý, đọc chuột / bàn phím, cửa sổ và tiến trình đang chạy."""

import atexit
import ctypes
import os
import sys
import threading
import traceback
from ctypes import wintypes

from .base import log
from .winapi import (
    EnumWindowsProc, GWL_EXSTYLE, GW_OWNER, PROCESS_QUERY_LIMITED_INFORMATION, WS_EX_TOOLWINDOW,
    force_show_cursor, kernel32, mag, user32)
from .syscursor import restore_system_cursors


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
    try:
        force_show_cursor()
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

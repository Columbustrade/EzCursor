"""Chế độ "Con trỏ thật": thay con trỏ Windows bằng con trỏ EzCursor.

Đang ẩn (REAL_CURSOR_MODE = False), giữ lại để dành cho bản sau."""

import ctypes
from ctypes import wintypes

from PIL import Image

from .base import SYS_FLAG
from .winapi import BITMAPINFOHEADER, kernel32, user32


REAL_CURSOR_MODE = False      # chế độ "Con trỏ thật" đang ẩn (để dành); True = hiện lựa chọn trong tab Tùy chọn
SPI_SETCURSORS = 0x0057
IMAGE_CURSOR = 2
SYS_CURSOR_IDS = (32512, 32513, 32514, 32515, 32516, 32648, 32649, 32650, 32651)   # mũi tên, chữ I, chờ, thập...
_sys_applied = False


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


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


if SYS_FLAG.exists():
    restore_system_cursors(force=True)

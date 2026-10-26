"""Lớp phủ trong suốt vẽ con trỏ (UpdateLayeredWindow)."""

import ctypes
from ctypes import wintypes

from PIL import Image, ImageFilter

from .winapi import (
    BITMAPINFOHEADER, HWND_TOPMOST, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
    WS_EX_TRANSPARENT, kernel32, user32)
from .system import exe_name, pid_of


gdi32 = ctypes.windll.gdi32
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HANDLE), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HANDLE)]


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
        # taskbar, menu, khung xem trước... vừa nổi lên trên thì đưa con trỏ lên lại (kiểm tra rất nhẹ)
        if user32.GetTopWindow(None) != self.hwnd:
            self.raise_top()

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
shell_reason = [""]        # cửa sổ khiến EzCursor trả con trỏ Windows (ghi vào nhật ký để dò lỗi)


def shell_ui_open(keep_taskbar=False):
    """True khi giao diện riêng của Windows (Start, Search, taskbar, xem trước...) đang mở hoặc ở dưới chuột.
    keep_taskbar: rê chuột trên thanh taskbar vẫn giữ con trỏ EzCursor."""
    h = user32.GetForegroundWindow()
    if h:
        exe = exe_name(pid_of(h)).lower()
        cls = class_name(h)
        if exe in SHELL_UI_EXES or (exe in ("explorer.exe", "") and cls in SHELL_UI_CLASSES):
            shell_reason[0] = f"cửa sổ đang mở {exe} / {cls}"
            return True
    # Cửa sổ ngay dưới con trỏ: khung xem trước taskbar, khay hệ thống, thông báo... không lấy focus
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    under = user32.WindowFromPoint(pt)
    if under:
        root = user32.GetAncestor(under, 2) or under          # GA_ROOT
        cls = class_name(root)
        # Menu chuột phải và thông báo của Windows nằm trên cả lớp phủ (đã thử 26/10) -> dùng con trỏ thật
        if cls not in SHELL_HOVER_OK and not (keep_taskbar and cls in TASKBAR_CLASSES):
            exe = exe_name(pid_of(root)).lower()
            if exe in SHELL_UI_EXES or exe == "explorer.exe":
                shell_reason[0] = f"dưới chuột {exe} / {cls}"
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

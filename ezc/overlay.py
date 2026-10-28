"""Lớp phủ trong suốt vẽ con trỏ (UpdateLayeredWindow) và luồng riêng bám chuột."""

import collections
import ctypes
import math
import sys
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageFilter

from .base import log
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


user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
                                wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.MsgWaitForMultipleObjectsEx.argtypes = [wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                               wintypes.DWORD]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
PM_REMOVE, QS_ALLINPUT, MWMO_INPUTAVAILABLE = 0x1, 0x4FF, 0x4


def refresh_hz():
    """Tần số quét của màn hình chính (Hz)."""
    try:
        hdc = user32.GetDC(None)
        hz = ctypes.windll.gdi32.GetDeviceCaps(hdc, 116)          # VREFRESH
        user32.ReleaseDC(None, hdc)
        return hz if isinstance(hz, int) and 30 <= hz <= 500 else 60
    except Exception:
        return 60


class CursorFollower:
    """Luồng riêng bám chuột (~1 ms/lần): luồng này tạo và sở hữu cửa sổ con trỏ (self.ovl) nên dời cửa sổ
    không phải chờ luồng giao diện – giao diện bận dựng ảnh, đổi tab... con trỏ vẫn bám đều.
    Luồng giao diện chỉ đặt hot / find_hot / predict / on; gọi set_image, show... từ giao diện vẫn được
    (Windows chuyển lời gọi sang luồng này, luồng này xử lý trong vòng ~1 ms)."""

    def __init__(self):
        self.on = False             # True: đang bám chuột
        self.hot = (0, 0)           # điểm click trong ảnh con trỏ
        self.find_hot = None        # điểm click trong ảnh "tìm con trỏ" (đang chạy thì không đoán trước)
        self.predict = False
        self.ovl = None
        self.tid = 0
        self._stop = False
        self._gen = 0               # tăng mỗi lần giao diện yêu cầu dời ngay (kick)
        self._moved_gen = 0
        self._moved = threading.Event()
        self._last = None
        self._hist = collections.deque(maxlen=16)
        self._prev_v = (0.0, 0.0)
        self._hz = refresh_hz()
        self._perf = {"t0": None, "n": 0, "gap": 0.0, "last": None, "done": False}
        self._err = False
        # Python mặc định chỉ đổi luồng sau 5 ms: giảm xuống 1 ms để luồng bám chuột không phải chờ lâu
        # (cần cả timeBeginPeriod(1) ở system.py, nếu không Windows làm tròn lần chờ GIL lên ~16 ms)
        sys.setswitchinterval(0.001)
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(ready,), name="EzCursorFollow", daemon=True)
        self._thread.start()
        ready.wait(3)
        if self.ovl is None:
            raise RuntimeError("Không tạo được cửa sổ con trỏ")

    def set(self, on, predict):
        self.predict = predict
        if on != self.on:
            self.on = on
            self._wake()

    def kick(self, wait=True):
        """Dời cửa sổ con trỏ tới chuột ngay (vd vừa đổi ảnh); wait: chờ tối đa ~10 ms cho xong."""
        self._moved.clear()
        self._gen += 1
        gen = self._gen
        self._wake()
        if not (wait and self.on) or threading.current_thread() is self._thread:
            return
        end = time.perf_counter() + 0.01
        while self._moved_gen < gen and self.on and not self._stop:
            left = end - time.perf_counter()
            if left <= 0:
                break
            self._moved.wait(left)
            self._moved.clear()

    def stop(self):
        self._stop = True
        self._wake()
        self._thread.join(1)

    def _wake(self):
        if self.tid:
            user32.PostThreadMessageW(self.tid, 0, 0, 0)          # WM_NULL: đánh thức luồng đang chờ

    def _run(self, ready):
        try:
            self.tid = kernel32.GetCurrentThreadId()
            self.ovl = LayeredOverlay()
        finally:
            ready.set()
        msg = wintypes.MSG()
        pt = wintypes.POINT()
        t_top = 0.0
        while not self._stop:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            if not self.on:
                self._perf["last"] = None
                # chờ tới khi có yêu cầu từ luồng giao diện (set_image, show, kick...) hoặc tối đa 50 ms
                user32.MsgWaitForMultipleObjectsEx(0, None, 50, QS_ALLINPUT, MWMO_INPUTAVAILABLE)
                continue
            try:
                now = time.perf_counter()
                self._step(pt, now)
                if now - t_top >= 0.5:                # giữ cửa sổ con trỏ luôn trên cùng
                    t_top = now
                    self.ovl.raise_top()
                self._record_perf(now)
            except Exception:
                if not self._err:
                    self._err = True
                    log.exception("Lỗi luồng bám chuột")
            time.sleep(0.001)
        self.ovl.destroy()

    def _step(self, pt, now):
        gen = self._gen
        user32.GetCursorPos(ctypes.byref(pt))
        x, y = pt.x, pt.y
        hot = self.find_hot or self.hot
        if self.predict and self.find_hot is None:
            x, y = self._predicted(x, y, now)
        key = (x, y, hot)
        if key != self._last or gen != self._moved_gen:
            self._last = key
            self.ovl.move(int(x - hot[0]), int(y - hot[1]))
        if gen != self._moved_gen:
            self._moved_gen = gen
            self._moved.set()

    def _predicted(self, x, y, now):
        """Đoán vị trí chuột sau ~nửa khung hình theo tốc độ hiện tại (đổi hướng / chậm thì không đoán)."""
        hist = self._hist
        hist.append((now, x, y))
        old = next((h for h in hist if now - h[0] <= 0.012), None)
        if old is None or now - old[0] < 0.003:
            return x, y
        dt = now - old[0]
        vx, vy = (x - old[1]) / dt, (y - old[2]) / dt
        pv = self._prev_v
        self._prev_v = (vx, vy)
        if vx * pv[0] + vy * pv[1] < 0 or (vx * vx + vy * vy) < 200 ** 2:     # đổi hướng hoặc rê chậm
            return x, y
        lead = 0.5 / self._hz
        dx, dy = vx * lead, vy * lead
        m = math.hypot(dx, dy)
        if m > 40:
            dx, dy = dx * 40 / m, dy * 40 / m
        return int(round(x + dx)), int(round(y + dy))

    def _record_perf(self, now):
        """Đo nhịp bám chuột khi con trỏ đang hiện; ghi log một lần sau ~20 giây."""
        pf = self._perf
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
            log.info("Độ trễ lớp phủ (luồng riêng): bám chuột mỗi %.1f ms, chậm nhất %.0f ms, đoán trước: %s, "
                     "màn hình %d Hz", (now - pf["t0"]) * 1000 / max(1, pf["n"]), pf["gap"] * 1000,
                     "bật" if self.predict else "tắt", self._hz)


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

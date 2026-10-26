"""Menu khay hệ thống, cửa sổ chính (ẩn / hiện), màn hình chào."""

import ctypes
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

import pystray
from PIL import Image, ImageTk

from .. import i18n
from ..base import APP_NAME, APP_VERSION, res_path
from ..winapi import GWL_EXSTYLE, user32
from ..i18n import T
from ..config import my_cursor_files
from ..theme import ACCENT, BG, BORDER, MUTED, TEXT
from ..icons import logo_frames
from ..bibata import OWN_CURSORS


class TrayMixin:
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
        return (i18n.LANG, self.enabled, c["shape"], c["image"], c["bibata_cursor"], tuple(c["favorites"]), id(self.tray_pr),
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

"""Lớp App (ghép từ các mixin) và hàm main() khởi động EzCursor."""

import ctypes
import gc
import logging
import logging.handlers
import os
import platform
import queue
import sys
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import pystray

from . import i18n
from .base import APP_DIR, APP_NAME, APP_VERSION, QUIT_FLAG, SHOW_FLAG, log, res_path
from .winapi import ERROR_ALREADY_EXISTS, kernel32, user32
from .system import cleanup
from .i18n import T
from .config import ProfileCfg, load_cfg, migrate_old_version, write_cfg
from .display import make_tray_icon
from .theme import BG, Fonts, load_fonts
from .icons import logo_frames
from .overlay import CursorFollower, LayeredOverlay
from .fx import FxEngine
from .ui.widgets import WidgetsMixin
from .ui.tray import TrayMixin
from .ui.profiles import ProfilesMixin
from .ui.cursor_tab import CursorTabMixin
from .ui.library import LibraryMixin
from .ui.catalog_ui import CatalogMixin
from .ui.maker_ui import MakerMixin
from .ui.effects import EffectsMixin
from .ui.apps import AppsMixin
from .ui.options import OptionsMixin
from .ui.hotkeys_ui import HotkeysMixin
from .ui.wizard import WizardMixin
from .ui.render import RenderMixin
from .ui.tracking import TrackingMixin
from .ui.find import FindMixin
from .ui.update import UpdateMixin
from .ui.errors import ErrorsMixin
from .ui.syscursor_ui import SysCursorMixin


class App(
        WidgetsMixin, TrayMixin, ProfilesMixin, CursorTabMixin, LibraryMixin, CatalogMixin, MakerMixin,
        EffectsMixin, AppsMixin, OptionsMixin, HotkeysMixin, WizardMixin, RenderMixin, TrackingMixin,
        FindMixin, UpdateMixin, ErrorsMixin, SysCursorMixin):
    """Cửa sổ EzCursor. Mỗi nhóm chức năng nằm trong một mixin ở ezc/ui/."""

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
        i18n.LANG = self.cfg["language"]
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
        # Bộ dọn rác tự động chạy ở luồng nào đang tạo đối tượng, kể cả luồng bám chuột: nếu nó dọn đối tượng Tk ở đó
        # thì luồng bám chuột phải chờ Tk (có thể kẹt cả hai). Tắt tự động, tự dọn ở vòng lặp chính (tick_body).
        gc.disable()
        self.t_gc = 0.0
        self.gc_n = 0
        self.fxw = LayeredOverlay()      # lớp hiệu ứng, tạo trước để nằm dưới con trỏ
        self.follow = CursorFollower()   # luồng riêng bám chuột, sở hữu cửa sổ con trỏ
        self.ovl = self.follow.ovl
        self.fx = FxEngine()
        self.fx_test_until = 0.0
        self.fx_prev_click = False
        self.fx_t = time.perf_counter()
        self.composed = None
        self.cursor_frames = None
        self.preview_photos = None
        self.cf_idx = 0
        self.variants = {}          # None / "left" / "right" -> (ảnh, điểm click, màu quầng)
        self.frame_sets = None      # các bộ khung hình động theo trạng thái giữ chuột
        self.hold_state = None
        self.shown_img = None       # ảnh con trỏ đang hiển thị (không tính hiệu ứng tìm con trỏ)
        self.find_t0 = None         # thời điểm bắt đầu hiệu ứng tìm con trỏ
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

        self.load_style_image()

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
        self.ov.after(5000, self.auto_check_update)
        if not self.cfg["setup_done"] or "--setup" in sys.argv:
            self.ov.after(700, self.wait_setup)

    def save(self):
        self.cfg["enabled"] = self.enabled
        try:
            write_cfg(self.cfg.base)
        except Exception as e:
            if not getattr(self, "save_warned", False):     # chỉ ghi nhật ký lần đầu, tránh đầy log
                self.save_warned = True
                log.warning("Không lưu được cài đặt: %s", e)

    def open_log_folder(self):
        try:
            os.startfile(str(APP_DIR))
        except Exception as e:
            messagebox.showerror(T("Lỗi"), str(e), parent=self.win)

    def quit(self):
        self.quitting = True
        log.info("Thoát EzCursor.")
        cleanup()
        self.follow.stop()               # luồng bám chuột tự hủy cửa sổ con trỏ của nó
        gc.enable()
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

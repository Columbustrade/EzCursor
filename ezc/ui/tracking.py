"""Vòng lặp chính: nhận biết game đang chơi, bám chuột, đoán trước vị trí, hoạt ảnh."""

import ctypes
import gc
import time
import tkinter as tk
from ctypes import wintypes

from ..base import APP_NAME, QUIT_FLAG, SHOW_FLAG, log
from ..winapi import show_real_cursor, user32
from ..syscursor import REAL_CURSOR_MODE
from ..system import foreground_exe, mouse_buttons
from ..i18n import T
from ..colors import mix
from ..display import fullscreen_exclusive
from ..theme import FIELD
from ..overlay import shell_reason, shell_ui_open


class TrackingMixin:
    def compute_active(self):
        if not self.enabled:
            return False
        self.shell_open = shell_ui_open(self.cfg["keep_taskbar"])
        if self.shell_open:          # menu Start, Search, Alt+Tab... -> dùng con trỏ thật
            if shell_reason[0] != getattr(self, "shell_logged", None):
                self.shell_logged = shell_reason[0]
                log.info("Dùng con trỏ Windows: %s", shell_reason[0])
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
        self.move_overlay()          # bật / tắt luồng bám chuột (và dời con trỏ tới chuột trước khi hiện)
        if not self.system_mode():
            self.ovl.show(on)
        self.update_status()

    # Điểm click của ảnh con trỏ nằm ở luồng bám chuột: đổi ở đây là luồng đó dùng ngay
    @property
    def ov_hot(self):
        return self.follow.hot

    @ov_hot.setter
    def ov_hot(self, hot):
        self.follow.hot = hot

    @property
    def find_hot(self):
        return self.follow.find_hot

    @find_hot.setter
    def find_hot(self, hot):
        self.follow.find_hot = hot

    def move_overlay(self):
        """Báo luồng bám chuột trạng thái mới và chờ nó dời con trỏ tới chuột (vd vừa đổi ảnh)."""
        on = self.find_t0 is not None or (self.active and not self.system_mode())
        self.follow.set(on, self.cfg["predict"])
        self.follow.kick()

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

    def collect_garbage(self, now):
        """Dọn rác ở luồng giao diện thay cho bộ dọn tự động (đã tắt, xem App.__init__)."""
        if gc.get_count()[0] >= 2000 or now - self.t_gc >= 1:
            self.t_gc = now
            self.gc_n += 1
            gc.collect(2 if self.gc_n % 60 == 0 else 1)     # dọn toàn bộ ~1 phút/lần

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
            self.collect_garbage(now)
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
        elif self.hold_state is not None:
            self.set_hold(None)
        return True

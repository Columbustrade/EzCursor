"""Vòng lặp chính: nhận biết game đang chơi, bám chuột, đoán trước vị trí, hoạt ảnh."""

import collections.abc
import ctypes
import math
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
            if on:
                self.move_overlay()
            self.ovl.show(on)
        self.update_status()

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

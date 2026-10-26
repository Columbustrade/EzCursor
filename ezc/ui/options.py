"""Tab Tùy chọn: ngôn ngữ, khởi động, độ trễ, đặt lại cài đặt."""

import ctypes
import subprocess
import sys
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import i18n
from ..base import APP_DIR, APP_NAME, APP_VERSION, ENTRY_SCRIPT
from ..winapi import show_real_cursor, user32
from ..syscursor import REAL_CURSOR_MODE
from ..startup import is_startup_enabled, set_startup
from ..i18n import LANGUAGES, T
from ..config import ProfileCfg, default_cfg, my_cursor_files
from ..colors import mix
from ..display import monitor_scale
from ..theme import ACCENT, CARD, FIELD, LINE, MUTED, TEXT, TEXT2


class OptionsMixin:
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
            args = f'"{pyw if pyw.exists() else sys.executable}" "{ENTRY_SCRIPT}"'
        # đợi bản hiện tại thoát hẳn rồi mới mở lại
        subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & start "" {args}',
                         shell=True, creationflags=0x08000000)
        self.quit()

    def set_language(self, code):
        """Đổi ngôn ngữ giao diện và dựng lại toàn bộ giao diện ngay, không cần khởi động lại."""
        if code == self.cfg["language"]:
            return
        self.cfg["language"] = code
        i18n.LANG = code
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

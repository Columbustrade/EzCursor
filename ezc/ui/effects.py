"""Tab Hiệu ứng và phần màu ombre."""

import ctypes
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import colorchooser, messagebox

import customtkinter as ctk

from ..base import APP_NAME
from ..winapi import SWP_NOACTIVATE, SWP_NOSIZE, user32
from ..system import mouse_buttons
from ..i18n import T
from ..colors import mix
from ..ombre import OMBRE_PRESETS, ombre_dot, ombre_swatch
from ..theme import ACCENT, BG, BORDER, CARD, FIELD, TEXT, TEXT2
from ..bibata import OWN_BY_ID
from ..fx import EZ_COLORS, FX_CLICKS, FX_TRAILS, fx_icon


class EffectsMixin:
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

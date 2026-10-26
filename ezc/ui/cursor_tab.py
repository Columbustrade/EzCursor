"""Khung giao diện chính, tab Con trỏ và các thao tác đổi kiểu con trỏ."""

import os
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from ..base import APP_NAME, APP_VERSION, MY_DIR, log
from ..i18n import T
from ..hotkeys import hotkey_parts
from ..config import DEFAULT_CFG, HOTSPOTS, SHAPES, TRANSPARENT, unique_my_path
from ..colors import mix
from ..curfile import load_cursor_file
from ..theme import (
    ACCENT, AMBER, BG, BORDER, CARD, CYAN, CYAN_TEXT, FIELD, GREEN, LINE, MUTED, SHAPE_BUTTONS, SIDEBAR,
    SWATCHES, TEXT, TEXT2)
from ..icons import logo_frames, logo_image, nav_icon, simple_icon
from ..bibata import OWN_BY_ID


class CursorTabMixin:
    def build_ui(self):
        self.win.grid_columnconfigure(1, weight=1)
        self.win.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.content = ctk.CTkFrame(self.win, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.pages = {
            "cursor": self.build_cursor_tab(self.content),
            "library": self.build_library_tab(self.content),
            "fx": self.build_fx_tab(self.content),
            "apps": self.build_apps_tab(self.content),
            "opts": self.build_options_tab(self.content),
        }
        self.update_profile_menus()
        self.show_tab("cursor")

    def build_sidebar(self):
        sb = ctk.CTkFrame(self.win, fg_color=SIDEBAR, corner_radius=0, width=230,
                          border_width=0)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)
        sb.pack_propagate(False)
        ctk.CTkFrame(self.win, fg_color=LINE, width=1, corner_radius=0).grid(row=0, column=0, sticky="nse")

        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(20, 18))
        self.logo_ctk = [ctk.CTkImage(fr.resize((64, 64), Image.LANCZOS), size=(30, 30)) for fr in logo_frames()]
        self.logo_lbl = ctk.CTkLabel(logo, text="", image=self.logo_ctk[0] if self.logo_ctk
                                     else ctk.CTkImage(logo_image(64), size=(30, 30)))
        self.logo_lbl.pack(side="left")
        ctk.CTkLabel(logo, text=" EZ", font=self.F.h(18), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(logo, text="CURSOR", font=self.F.h(18), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(logo, text=f"v{APP_VERSION}", font=self.F.m(10), text_color=MUTED,
                     fg_color="#151922", corner_radius=6, width=10).pack(side="left", padx=(8, 0))

        self.caps(sb, "MENU").pack(anchor="w", padx=24, pady=(0, 6))
        self.nav_buttons = {}
        for key, label in (("cursor", "Con trỏ"), ("library", "Bộ sưu tập"), ("fx", "Hiệu ứng"),
                           ("apps", "Ứng dụng"), ("opts", "Tùy chọn")):
            icons = (ctk.CTkImage(nav_icon(key, "#FFFFFF", 40), size=(20, 20)),
                     ctk.CTkImage(nav_icon(key, TEXT2, 40), size=(20, 20)))
            b = ctk.CTkButton(sb, text="  " + T(label), anchor="w", height=46, corner_radius=10,
                              font=self.F.b(14, strong=True), border_width=1,
                              command=lambda k=key: self.show_tab(k))
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = (b, icons)

        # Khung trạng thái
        st = ctk.CTkFrame(sb, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=12)
        st.pack(side="bottom", fill="x", padx=14, pady=16)
        self.caps(st, "TRẠNG THÁI").pack(anchor="w", padx=14, pady=(12, 6))
        self.pill = ctk.CTkLabel(st, text="", font=self.F.h(12), corner_radius=14, height=28)
        self.pill.pack(anchor="w", padx=14)
        self.status_sub = ctk.CTkLabel(st, text="", font=self.F.b(12), text_color=TEXT2,
                                       wraplength=int(170 * 1), justify="left")
        self.status_sub.pack(anchor="w", padx=14, pady=(6, 8))
        row = ctk.CTkFrame(st, fg_color="transparent")
        row.pack(fill="x", padx=14)
        ctk.CTkLabel(row, text=T("Bật EzCursor"), font=self.F.b(14, strong=True), text_color=TEXT).pack(side="left")
        self.enabled_var = tk.BooleanVar(value=self.enabled)
        self.switch(row, self.enabled_var, self.on_enabled_switch).pack(side="right")
        self.toggle_hint = ctk.CTkLabel(st, text=" + ".join(hotkey_parts(self.cfg["hotkeys"]["toggle"], "toggle")),
                                        font=self.F.m(11), text_color=MUTED)
        self.toggle_hint.pack(anchor="w", padx=14, pady=(4, 12))

    def build_cursor_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.page_top(page, "CON TRỎ", "Chọn hình dạng, màu sắc và kích thước con trỏ trong game.", (0, 16))
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure((0, 1), weight=1, uniform="c")

        # --- Xem trước
        pv = self.card(body)
        pv.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        top = ctk.CTkFrame(pv, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 8))
        self.caps(top, "XEM TRƯỚC").pack(side="left")
        ctk.CTkLabel(top, text="LIVE", font=self.F.m(11), text_color=CYAN).pack(side="right")
        sc = self.sc
        self.pw, self.ph = int(self.PW * sc), int(self.PH * sc)
        self.pcv = tk.Canvas(pv, width=self.pw, height=self.ph, bg=FIELD, highlightthickness=1,
                             highlightbackground=BORDER, bd=0)
        self.pcv.pack(padx=14, pady=(0, 14))
        self.build_preview_canvas()
        self.build_ombre_box(pv)

        # --- Điều khiển
        ctl = self.card(body)
        ctl.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        inner = ctk.CTkFrame(ctl, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        self.caps(inner, "HÌNH DẠNG").pack(anchor="w")
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x", pady=(6, 14))
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.shape_buttons = {}
        for i, (shape, label) in enumerate(SHAPE_BUTTONS):
            b = ctk.CTkButton(grid, text=T(label), height=38, width=10, corner_radius=9, border_width=1,
                              font=self.F.b(13, strong=True), command=lambda s=shape: self.set_shape(s))
            b.grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)
            self.shape_buttons[shape] = b

        self.caps(inner, "MÀU SẮC").pack(anchor="w")
        sw = ctk.CTkFrame(inner, fg_color="transparent")
        sw.pack(fill="x", pady=(6, 14))
        self.swatch_buttons = {}
        for c, name in SWATCHES:
            b = ctk.CTkButton(sw, text="", width=34, height=34, corner_radius=17, fg_color=c,
                              hover_color=mix(c, "#FFFFFF", 0.2), border_width=0,
                              command=lambda c=c: self.set_color(c))
            b.pack(side="left", padx=(0, 7))
            self.swatch_buttons[c] = b
        self.custom_btn = ctk.CTkButton(sw, text="", width=34, height=34, corner_radius=17,
                                        image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)),
                                        fg_color="transparent", hover_color="#1A1E29",
                                        border_width=1, border_color="#4A5266", command=self.pick_color)
        self.custom_btn.pack(side="left")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.caps(row, "KÍCH THƯỚC").pack(side="left")
        self.size_label = ctk.CTkLabel(row, text="", font=self.F.m(12), text_color=ACCENT)
        self.size_label.pack(side="right")
        self.size_slider = ctk.CTkSlider(inner, from_=24, to=160, number_of_steps=136,
                                         command=lambda v: self.set_size(int(v)), progress_color=ACCENT,
                                         button_color=ACCENT, button_hover_color=mix(ACCENT, "#FFFFFF", 0.25),
                                         fg_color="#1A1E29", height=18)
        self.size_slider.set(self.cfg["size"])
        self.size_slider.pack(fill="x", pady=(4, 14))

        self.caps(inner, "ẢNH TÙY CHỈNH").pack(anchor="w")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(6, 6))
        self.cyan_button(row, "Tải ảnh lên", self.upload_image,
                         ctk.CTkImage(simple_icon("upload", CYAN_TEXT, 32), size=(16, 16))).pack(side="left")
        self.img_label = ctk.CTkLabel(row, text=T("(chưa có ảnh)"), font=self.F.m(12), text_color=TEXT2)
        self.img_label.pack(side="left", padx=10)
        if self.cfg["image"] and self.src_img is not None:
            self.img_label.configure(text=Path(self.cfg["image"]).name)

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(row, text=T("Điểm click"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.hot_map = {T(h): h for h in HOTSPOTS}
        self.hot_seg = ctk.CTkSegmentedButton(row, values=list(self.hot_map),
                                              command=lambda v: self.set_hotspot(self.hot_map[v]), height=30,
                                              font=self.F.b(12), fg_color=FIELD, unselected_color=FIELD,
                                              unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                                              selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        self.hot_seg.set(T(self.cfg["hotspot"]))
        self.hot_seg.pack(side="right")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(row, text=T("Tô màu cho ảnh tải lên"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.tint_var = tk.BooleanVar(value=self.cfg["tint_image"])
        self.switch(row, self.tint_var, self.set_tint).pack(side="right")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text=T("Quầng sáng quanh con trỏ"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.glow_var = tk.BooleanVar(value=self.cfg["glow"])
        self.switch(row, self.glow_var, self.set_glow).pack(side="right")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text=T("Phóng theo tỉ lệ màn hình"), font=self.F.b(13), text_color=TEXT).pack(side="left")
        self.dpi_var = tk.BooleanVar(value=self.cfg["dpi_scale"])
        self.switch(row, self.dpi_var, self.set_dpi_scale).pack(side="right")
        return page

    def build_preview_canvas(self):
        c, w, h, sc = self.pcv, self.pw, self.ph, self.sc
        step = int(22 * sc)
        gcol = mix(FIELD, CYAN, 0.07)
        for x in range(w // 2 % step, w, step):
            c.create_line(x, 0, x, h, fill=gcol)
        for y in range(h // 2 % step, h, step):
            c.create_line(0, y, w, y, fill=gcol)
        L, m, t = int(18 * sc), int(12 * sc), max(2, int(2 * sc))
        for x0, y0, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            c.create_line(x0, y0, x0 + dx * L, y0, fill=CYAN, width=t)
            c.create_line(x0, y0, x0, y0 + dy * L, fill=CYAN, width=t)
        self.scan = c.create_line(0, 0, w, 0, fill=mix(FIELD, CYAN, 0.35), width=max(1, int(2 * sc)))
        self.ping = c.create_oval(0, 0, 0, 0, outline=ACCENT, width=max(2, int(2 * sc)))
        self.pimg_id = c.create_image(w // 2, h // 2)
        mono = (self.F.mono, 9)
        self.coord_txt = c.create_text(int(16 * sc), h - int(30 * sc), anchor="w", text="", fill=CYAN_TEXT, font=mono)
        self.size_txt = c.create_text(w - int(16 * sc), h - int(30 * sc), anchor="e", text="", fill=CYAN_TEXT, font=mono)

    def show_tab(self, key):
        self.tab = key
        for k, page in self.pages.items():
            if k == key:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        for k, (b, icons) in self.nav_buttons.items():
            if k == key:
                b.configure(fg_color=mix(SIDEBAR, ACCENT, 0.14), hover_color=mix(SIDEBAR, ACCENT, 0.2),
                            border_color=ACCENT, text_color="#FFFFFF", image=icons[0])
            else:
                b.configure(fg_color="transparent", hover_color="#161A23", border_color=SIDEBAR,
                            text_color=TEXT2, image=icons[1])
        if key == "apps":
            self.refresh_apps()

    def update_app_set(self):
        self.app_set = {a.lower() for a in self.cfg["apps"]}

    def status_info(self):
        if not self.enabled:
            return T("●  ĐANG TẮT"), MUTED, T("Con trỏ gốc đang được dùng.")
        if self.active:
            sub = T("Áp dụng cho mọi ứng dụng.") if self.cfg["all_apps"] else T("Trong game: ") + self.fg_exe
            pr = self.profile_for_exe(self.fg_exe)
            if pr:
                sub += "\n" + T("Hồ sơ: ") + pr["name"]
            return T("●  ĐANG HOẠT ĐỘNG"), GREEN, sub
        if self.shell_open:
            return T("●  TẠM DỪNG"), AMBER, T("Đang ở trên giao diện của Windows.")
        if self.fs_block:
            return T("●  FULLSCREEN"), AMBER, T("Game đang ở Fullscreen. Hãy chuyển sang Borderless hoặc Windowed.")
        if not self.cfg["apps"]:
            return T("●  CHƯA CHỌN GAME"), AMBER, T("Vào tab Ứng dụng để chọn game.")
        return T("●  ĐANG CHỜ GAME"), AMBER, T("Chờ: ") + ", ".join(self.cfg["apps"])

    def update_status(self, blink=False):
        text, col, sub = self.status_info()
        dot = mix(col, CARD, 0.6) if blink else col
        self.pill.configure(text=f"  {text}  ", text_color=dot if blink else col,
                            fg_color=mix(CARD, col, 0.14))
        self.status_sub.configure(text=sub)

    def update_preview(self):
        c = self.cfg
        if self.composed is None:
            self.rebuild_overlay()
        im = self.composed[0]
        self.pimg = ImageTk.PhotoImage(im, master=self.ov)
        self.pcv.itemconfig(self.pimg_id, image=self.pimg)
        self.pcv.itemconfig(self.size_txt, text=f"{c['size']} PX")

    def update_controls(self):
        c = self.cfg
        for shape, b in self.shape_buttons.items():
            if shape == c["shape"]:
                b.configure(fg_color=mix(CARD, ACCENT, 0.16), hover_color=mix(CARD, ACCENT, 0.24),
                            border_color=ACCENT, text_color="#FFFFFF")
            else:
                b.configure(fg_color=FIELD, hover_color="#161A23", border_color=BORDER, text_color=TEXT2)
        # con trỏ đang dùng màu gốc (bộ EzCursor / chủ đề Bibata có sẵn) thì không ô màu nào sáng
        uses_color = not ((c["shape"] in OWN_BY_ID and c["own_theme"] == "original")
                          or (c["shape"] == "Bibata" and c["bibata_theme"] != "custom") or c["ombre"])
        for col, b in self.swatch_buttons.items():
            on = uses_color and col.lower() == c["color"].lower()
            b.configure(border_width=3 if on else 0, border_color="#FFFFFF")
        custom = uses_color and c["color"].lower() not in {x.lower() for x, _ in SWATCHES}
        if custom:
            self.custom_btn.configure(fg_color=c["color"], hover_color=c["color"], border_width=3,
                                      border_color="#FFFFFF", image=None)
        else:
            self.custom_btn.configure(fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                      border_color="#4A5266",
                                      image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)))
        self.size_label.configure(text=f"{c['size']} px")
        self.update_ombre_ui()

    def on_enabled_switch(self):
        if bool(self.enabled_var.get()) != self.enabled:
            self.toggle()

    def toggle(self):
        self.enabled = not self.enabled
        self.enabled_var.set(self.enabled)
        self.set_active(self.compute_active())
        self.refresh()
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def set_shape(self, shape):
        self.cfg["shape"] = shape
        self.refresh()

    def next_shape(self):
        favs = [f for f in self.cfg["favorites"] if self.fav_valid(f)]
        if favs:
            cur = self.current_fav_id()
            i = favs.index(cur) if cur in favs else -1
            self.use_fav(favs[(i + 1) % len(favs)])
            return
        options = [x for x in SHAPES if x != "Ảnh tải lên" or self.src_img is not None]
        cur = self.cfg["shape"]
        i = options.index(cur) if cur in options else -1
        self.set_shape(options[(i + 1) % len(options)])

    def set_color(self, color):
        if color.lower() == TRANSPARENT:
            color = "#020202"
        self.cfg["color"] = color
        self.cfg["ombre"] = False
        if self.cfg["shape"] == "Bibata":
            self.cfg["bibata_theme"] = "custom"
        elif self.cfg["shape"] in OWN_BY_ID:
            self.cfg["own_theme"] = "custom"
        self.refresh()

    def pick_color(self):
        res = colorchooser.askcolor(color=self.cfg["color"], parent=self.win, title=T("Chọn màu"))
        if res and res[1]:
            self.set_color(res[1])

    def set_size(self, s):
        if s == self.cfg["size"]:
            return
        self.cfg["size"] = s
        self.refresh()

    def set_tint(self):
        self.cfg["tint_image"] = bool(self.tint_var.get())
        self.refresh()

    def set_glow(self):
        self.cfg["glow"] = bool(self.glow_var.get())
        self.refresh()

    def set_hotspot(self, h):
        self.cfg["hotspot"] = h
        self.refresh()

    def upload_image(self):
        path = filedialog.askopenfilename(
            parent=self.win, title=T("Chọn ảnh con trỏ"),
            filetypes=[(T("Ảnh hoặc con trỏ"), "*.png *.gif *.webp *.ico *.cur *.ani *.bmp *.jpg *.jpeg"),
                       (T("Con trỏ Windows"), "*.cur *.ani"), (T("Tất cả"), "*.*")])
        if not path:
            return
        try:
            load_cursor_file(path)                    # thử đọc trước khi lưu
        except Exception as e:
            messagebox.showerror(T("Lỗi"), T("Không mở được ảnh:") + f"\n{e}", parent=self.win)
            return
        try:
            MY_DIR.mkdir(parents=True, exist_ok=True)
            dest = unique_my_path(Path(path).name)
            shutil.copyfile(path, dest)
        except Exception as e:
            messagebox.showerror(T("Lỗi"), T("Không sao chép được ảnh:") + f"\n{e}", parent=self.win)
            return
        self.use_my_cursor(dest)
        self.rebuild_mine_tiles()

    def use_my_cursor(self, path):
        """Dùng một con trỏ trong "Con trỏ của bạn"."""
        path = Path(path)
        if not self.load_image(str(path)):
            return
        self.cfg["image"] = str(path)
        self.img_label.configure(text=path.name)
        if self.src_hot is not None:
            self.cfg["hotspot"] = "Theo file"
        elif self.cfg["hotspot"] == "Theo file":
            self.cfg["hotspot"] = HOTSPOTS[0]
        self.hot_seg.set(T(self.cfg["hotspot"]))
        self.set_shape("Ảnh tải lên")

    def delete_my_cursor(self):
        img = self.cfg["image"]
        if not (self.cfg["shape"] == "Ảnh tải lên" and img and Path(img).parent == MY_DIR):
            return
        if not messagebox.askyesno(APP_NAME, T("Xóa con trỏ \"{n}\" khỏi bộ sưu tập?").format(n=Path(img).stem),
                                   parent=self.win):
            return
        try:
            Path(img).unlink()
        except OSError:
            pass
        self.cfg["favorites"] = [f for f in self.cfg["favorites"] if f != "my:" + Path(img).name]
        self.cfg["made_cursors"] = {k: v for k, v in self.cfg["made_cursors"].items() if k != Path(img).name}
        self.cfg["catalog_got"] = {k: v for k, v in self.cfg["catalog_got"].items() if v != Path(img).name}
        for st in [self.cfg.base] + [pr["style"] for pr in self.cfg["profiles"]]:
            if st.get("image") == img:
                st["image"] = ""
                if st.get("shape") == "Ảnh tải lên":
                    st["shape"] = "EzDrop"
        self.img_cache.clear()
        self.clear_image()
        self.img_label.configure(text=T("(chưa có ảnh)"))
        self.rebuild_mine_tiles()
        self.refresh()

    def clear_image(self):
        self.src_img = self.src_frames = self.src_steps = self.src_hot = None

    def load_style_image(self):
        """Nạp ảnh của bộ kiểu đang chọn; file mất hoặc hỏng thì quay về con trỏ mặc định thay vì báo lỗi."""
        img = self.cfg["image"]
        if img and self.load_image(img, silent=True):
            return
        self.clear_image()
        if img:
            log.warning("Không mở được ảnh con trỏ %s, dùng con trỏ mặc định", img)
            self.cfg["image"] = ""
        if self.cfg["shape"] == "Ảnh tải lên":
            self.cfg["shape"] = DEFAULT_CFG["shape"]

    def load_image(self, path, silent=False):
        try:
            key = (path, os.path.getmtime(path))
            if key not in self.img_cache:
                if len(self.img_cache) > 8:
                    self.img_cache.clear()
                self.img_cache[key] = load_cursor_file(path)
            frames, self.src_hot, steps = self.img_cache[key]
            self.src_img = frames[0]
            self.src_frames, self.src_steps = (frames, steps) if steps and len(frames) > 1 else (None, None)
        except Exception as e:
            self.src_img = self.src_frames = self.src_steps = self.src_hot = None
            if not silent:
                messagebox.showerror(T("Lỗi"), T("Không mở được ảnh:") + f"\n{e}", parent=self.win)
            return False
        return True

    def show_img(self, im):
        """Đặt ảnh con trỏ; trong lúc hiệu ứng tìm con trỏ chạy thì chỉ ghi nhớ, vẽ lại khi xong."""
        self.shown_img = im
        if self.find_t0 is None:
            self.ovl.set_image(im)

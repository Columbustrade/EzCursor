"""Tab Bộ sưu tập: Bibata, Con trỏ của bạn, Yêu thích."""

import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser

import customtkinter as ctk
from PIL import Image

from ..base import MY_DIR
from ..i18n import T
from ..config import my_cursor_files
from ..colors import mix
from ..ombre import apply_ombre, ombre_lut, ombre_swatch, ombre_tmap
from ..maker import maker_render
from ..curfile import load_cursor_file
from ..theme import ACCENT, BORDER, CARD, CYAN, CYAN_TEXT, FIELD, SWATCHES, TEXT, TEXT2
from ..icons import simple_icon, star_icon
from ..bibata import (
    BIBATA_CURSORS, BIBATA_DIR, BIBATA_META, BIBATA_THEMES, OWN_BY_ID, OWN_CURSORS, bibata_colors,
    bibata_image, own_image, own_image_colored)


class LibraryMixin:
    def build_library_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        self.page_top(page, "BỘ SƯU TẬP", "Con trỏ của EzCursor và bộ Bibata. Bấm vào con trỏ muốn dùng.", (0, 12))
        self.bib_tiles, self.own_tiles = {}, {}
        if getattr(self, "lib_view", None) is None:
            self.lib_view = {"Bibata": "bibata", "Ảnh tải lên": "mine"}.get(self.cfg["shape"], "ez")
        has_bib = BIBATA_DIR.exists()

        seg_kw = dict(height=34, font=self.F.b(12, strong=True), fg_color=FIELD, unselected_color=FIELD,
                      unselected_hover_color="#1A1E29", selected_color=mix(CARD, ACCENT, 0.35),
                      selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT)
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        self.view_map = {T("Bộ EzCursor"): "ez", "Bibata": "bibata", T("Của bạn"): "mine", T("Trực tuyến"): "online"}
        if not has_bib:
            del self.view_map["Bibata"]
        self.view_seg = ctk.CTkSegmentedButton(head, values=list(self.view_map),
                                               command=lambda v: self.set_lib_view(self.view_map[v]),
                                               **dict(seg_kw, height=36, font=self.F.b(13, strong=True)))
        self.view_seg.pack(side="left")
        self.view_seg.set({v: k for k, v in self.view_map.items()}[self.lib_view])

        # Hàng chủ đề: mỗi nhóm một bộ nút
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x")
        self.theme_caps = self.caps(top, "CHỦ ĐỀ")
        self.theme_caps.pack(anchor="w")
        self.chip_rows = {}
        self.theme_buttons, self.own_theme_buttons = {}, {}
        for view in ("ez", "bibata", "mine", "online"):
            row = ctk.CTkFrame(top, fg_color="transparent")
            self.chip_rows[view] = row
        self.cyan_button(self.chip_rows["online"], "Làm mới", lambda: self.start_catalog(force=True),
                         ctk.CTkImage(simple_icon("refresh", CYAN_TEXT, 32), size=(16, 16))).pack(side="left")
        self.cat_label = ctk.CTkLabel(self.chip_rows["online"], text="", font=self.F.b(12), text_color=TEXT2,
                                      wraplength=520, justify="left")
        self.cat_label.pack(side="left", padx=(12, 0))
        self.mine_theme_buttons = {}
        for key, label in (("original", T("Màu gốc")), ("tint", T("Tô màu"))):
            b = ctk.CTkButton(self.chip_rows["mine"], text=label, height=40, width=130, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_mine_tint(k == "tint"))
            b.pack(side="left", padx=(0, 8))
            self.mine_theme_buttons[key] = b
        self.mine_edit = ctk.CTkButton(head, text=T("Sửa con trỏ này"), command=self.edit_made_cursor, height=36,
                                       corner_radius=10, border_width=1, border_color=ACCENT,
                                       fg_color=mix(CARD, ACCENT, 0.10), hover_color=mix(CARD, ACCENT, 0.22),
                                       text_color="#FFFFFF", font=self.F.b(12, strong=True))
        self.mine_del = ctk.CTkButton(head, text=T("Xóa con trỏ này"), command=self.delete_my_cursor, height=36,
                                      corner_radius=10, border_width=1, border_color="#FF5A5A",
                                      fg_color=mix(CARD, "#FF5A5A", 0.10), hover_color=mix(CARD, "#FF5A5A", 0.22),
                                      text_color="#FF8A8A", font=self.F.b(12, strong=True),
                                      image=ctk.CTkImage(simple_icon("trash", "#FF8A8A", 32), size=(14, 14)))
        own_themes = [("original", T("Màu gốc")), ("custom", T("Tùy chỉnh"))]
        for key, label in own_themes:
            b = ctk.CTkButton(self.chip_rows["ez"], text=label, height=40, width=130, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_own_theme(k))
            b.pack(side="left", padx=(0, 8))
            self.own_theme_buttons[key] = b
        self.ombre_chips = []
        for view in ("ez", "bibata", "mine"):
            b = ctk.CTkButton(self.chip_rows[view], text="Ombre", height=40, width=118, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda v=view: self.lib_ombre(v))
            self.ombre_chips.append(b)
        themes = [(k, v[0]) for k, v in BIBATA_THEMES.items()] + [("custom", T("Tùy chỉnh"))]
        for key, label in themes:
            b = ctk.CTkButton(self.chip_rows["bibata"], text=label, height=40, width=118, corner_radius=10,
                              border_width=1, font=self.F.b(13, strong=True), compound="left",
                              command=lambda k=key: self.set_bib("bibata_theme", k))
            b.pack(side="left", padx=(0, 8))
            self.theme_buttons[key] = b
        for b in self.ombre_chips:
            b.pack(side="left", padx=(0, 8))

        self.sw_caps = self.caps(page, "MÀU TÙY CHỈNH")
        self.sw_caps.pack(anchor="w", pady=(12, 0))
        sw = ctk.CTkFrame(page, fg_color="transparent")
        sw.pack(fill="x", pady=(6, 12))
        self.sw_row = sw
        self.bib_swatches = {}
        for c, name in SWATCHES:
            b = ctk.CTkButton(sw, text="", width=32, height=32, corner_radius=16, fg_color=c,
                              hover_color=mix(c, "#FFFFFF", 0.2), border_width=0,
                              command=lambda c=c: self.set_bib_color(c))
            b.pack(side="left", padx=(0, 7))
            self.bib_swatches[c] = b
        for c in ("#FFFFFF", "#000000"):
            b = ctk.CTkButton(sw, text="", width=32, height=32, corner_radius=16, fg_color=c,
                              hover_color=mix(c, "#808080", 0.25), border_width=1, border_color="#4A5266",
                              command=lambda c=c: self.set_bib_color(c))
            b.pack(side="left", padx=(0, 7))
            self.bib_swatches[c] = b
        self.bib_custom_btn = ctk.CTkButton(sw, text="", width=32, height=32, corner_radius=16,
                                            image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)),
                                            fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                            border_color="#4A5266", command=self.pick_bib_color)
        self.bib_custom_btn.pack(side="left")
        # Kiểu Bibata nằm cùng hàng ô màu, chỉ hiện ở nhóm Bibata
        self.bib_opts = ctk.CTkFrame(head, fg_color="transparent")
        self.style_map = {T("Modern · bo tròn"): "modern", T("Original · góc nhọn"): "original"}
        self.hand_map = {T("Thuận tay phải"): "right", T("Thuận tay trái"): "left"}
        small = dict(seg_kw, height=36, font=self.F.b(12, strong=True))
        self.hand_seg = ctk.CTkSegmentedButton(self.bib_opts, values=list(self.hand_map),
                                               command=lambda v: self.set_bib("bibata_hand", self.hand_map[v]), **small)
        self.hand_seg.pack(side="right")
        self.style_seg = ctk.CTkSegmentedButton(self.bib_opts, values=list(self.style_map),
                                                command=lambda v: self.set_bib("bibata_style", self.style_map[v]), **small)
        self.style_seg.pack(side="right", padx=(0, 6))
        self.style_seg.set({v: k for k, v in self.style_map.items()}.get(self.cfg["bibata_style"], T("Modern · bo tròn")))
        self.hand_seg.set({v: k for k, v in self.hand_map.items()}.get(self.cfg["bibata_hand"], T("Thuận tay phải")))

        grid = self.card(page)
        grid.pack(fill="both", expand=True)
        self.lib_card = grid
        cols = 5
        self.lib_grids = {}
        for view in ("ez", "bibata", "mine", "online"):
            if view in ("mine", "online"):
                inner = ctk.CTkScrollableFrame(grid, fg_color="transparent", scrollbar_button_color=BORDER,
                                               scrollbar_button_hover_color="#3A4152")
            else:
                inner = ctk.CTkFrame(grid, fg_color="transparent")
            for i in range(cols):
                inner.grid_columnconfigure(i, weight=1, uniform="t")
            self.lib_grids[view] = inner
        self.mine_tiles = {}
        self.star_btns = {}
        for shape, label, _f, _h, _g in OWN_CURSORS:
            if own_image(shape) is None:
                continue
            n = len(self.own_tiles)
            b = ctk.CTkButton(self.lib_grids["ez"], text=T(label), compound="top", height=94, width=10,
                              corner_radius=12, border_width=1, font=self.F.b(12, strong=True),
                              command=lambda sh=shape: self.pick_own(sh))
            b.grid(row=n // cols, column=n % cols, sticky="ew", padx=4, pady=4)
            self.own_tiles[shape] = b
            self.add_star(b, shape)
        if has_bib:
            for i, (name, label) in enumerate(BIBATA_CURSORS):
                b = ctk.CTkButton(self.lib_grids["bibata"], text=T(label), compound="top", height=94, width=10,
                                  corner_radius=12, border_width=1, font=self.F.b(12),
                                  command=lambda n=name: self.pick_bibata(n))
                b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
                self.bib_tiles[name] = b
                self.add_star(b, "bib:" + name)

        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(foot, text=T("Bấm ☆ để thêm vào Yêu thích. Ctrl+Alt+R sẽ chỉ đổi giữa các con trỏ yêu thích."),
                     font=self.F.b(12), text_color=TEXT2).pack(side="left")
        self.bib_link = ctk.CTkLabel(foot, text="Bibata © Abdulkaiz Khatri · GPL-3.0", font=self.F.b(12),
                                     text_color=CYAN_TEXT, cursor="hand2")
        self.bib_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ful1e5/Bibata_Cursor"))
        self._lib_sig = None
        self._own_sig = None
        self.rebuild_mine_tiles()
        self.cat_tiles = {}
        self.build_online_tiles()
        self.show_lib_view()
        return page

    def rebuild_mine_tiles(self):
        """Dựng lại lưới "Của bạn": ô Thêm + mỗi con trỏ đã lưu."""
        self.mine_sig += 1
        grid = getattr(self, "lib_grids", {}).get("mine")
        if grid is None:
            return
        for w in grid.winfo_children():
            w.destroy()
        self.mine_tiles = {}
        self.star_btns = {k: v for k, v in getattr(self, "star_btns", {}).items() if not k.startswith("my:")}
        cols = 5
        make = ctk.CTkButton(grid, text=T("✦ Tạo con trỏ"), compound="top", height=94, width=10, corner_radius=12,
                             border_width=1, border_color=mix(BORDER, ACCENT, 0.6), fg_color=mix(CARD, ACCENT, 0.08),
                             hover_color=mix(CARD, ACCENT, 0.18), text_color="#FFFFFF", font=self.F.b(12, strong=True),
                             image=ctk.CTkImage(maker_render({"fill": "ombre", "in_w": 9, "out_w": 0, "shadow": False},
                                                             64)[0], size=(32, 32)),
                             command=self.open_maker)
        make.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        add = ctk.CTkButton(grid, text=T("+ Thêm con trỏ"), compound="top", height=94, width=10, corner_radius=12,
                            border_width=1, border_color=mix(BORDER, CYAN, 0.5), fg_color=mix(CARD, CYAN, 0.06),
                            hover_color=mix(CARD, CYAN, 0.16), text_color=CYAN_TEXT, font=self.F.b(12, strong=True),
                            image=ctk.CTkImage(simple_icon("upload", CYAN_TEXT, 64), size=(30, 30)),
                            command=self.upload_image)
        add.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        files = my_cursor_files()
        for i, f in enumerate(files, start=2):
            try:
                frames, _hot, _steps = load_cursor_file(str(f))
                th = frames[0].copy()
                th.thumbnail((112, 112), Image.LANCZOS)
                pic = Image.new("RGBA", (112, 112), (0, 0, 0, 0))
                pic.alpha_composite(th, ((112 - th.width) // 2, (112 - th.height) // 2))
            except Exception:
                continue
            name = f.stem if len(f.stem) <= 16 else f.stem[:14] + "…"
            b = ctk.CTkButton(grid, text=name, compound="top", height=94, width=10, corner_radius=12,
                              border_width=1, font=self.F.b(12), image=ctk.CTkImage(pic, size=(56, 56)),
                              command=lambda p=f: self.use_my_cursor(p))
            b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            self.mine_tiles[str(f)] = b
            self.add_star(b, "my:" + f.name)
        if not files:
            ctk.CTkLabel(grid, text=T("Chưa có con trỏ nào. Tự tạo một con trỏ, hoặc bấm \"+ Thêm con trỏ\" "
                                      "để thêm ảnh PNG, GIF hay file .cur, .ani."), font=self.F.b(12), text_color=TEXT2,
                         wraplength=360, justify="left").grid(row=0, column=2, columnspan=3, sticky="w", padx=12)
        self.update_library()

    def set_mine_tint(self, on):
        self.cfg["tint_image"] = on
        self.cfg["ombre"] = False
        try:
            self.tint_var.set(on)
        except AttributeError:
            pass
        self.refresh()

    def show_lib_view(self):
        v = self.lib_view
        for view, row in self.chip_rows.items():
            row.pack_forget()
        self.chip_rows[v].pack(fill="x", pady=(6, 0))
        if v == "online":
            self.theme_caps.pack_forget()
        else:
            self.theme_caps.pack(anchor="w", before=self.chip_rows[v])
        try:
            self.view_seg.set({k2: k for k, k2 in self.view_map.items()}[v])
        except (KeyError, tk.TclError):
            pass
        for view, g in self.lib_grids.items():
            g.pack_forget()
        self.lib_grids[v].pack(fill="both", expand=True, padx=10, pady=10)
        if v == "bibata":
            self.bib_opts.pack(side="right", anchor="e")
            self.bib_link.pack(side="right")
        else:
            self.bib_opts.pack_forget()
            self.bib_link.pack_forget()
        if v == "mine":
            self.mine_del.pack(side="right")
            self.mine_edit.pack(side="right", padx=(0, 8))
        else:
            self.mine_del.pack_forget()
            self.mine_edit.pack_forget()
        if v == "online":
            self.sw_caps.pack_forget()
            self.sw_row.pack_forget()
            if self.cat_entries is None and not self.cat_busy:
                self.start_catalog()
        elif not self.sw_row.winfo_ismapped():
            self.sw_caps.pack(anchor="w", pady=(12, 0), before=self.lib_card)
            self.sw_row.pack(fill="x", pady=(6, 12), before=self.lib_card)

    def set_lib_view(self, view):
        self.lib_view = view
        self.show_lib_view()
        self.update_library()

    def set_own_theme(self, theme):
        self.cfg["own_theme"] = theme
        self.cfg["ombre"] = False
        if self.cfg["shape"] not in OWN_BY_ID:
            self.cfg["shape"] = "EzDrop"
        self.refresh()

    def set_bib_color(self, color):
        self.cfg["color"] = color
        self.cfg["ombre"] = False
        if self.lib_view == "mine":
            self.set_mine_tint(True)
            return
        if self.lib_view == "ez":
            self.cfg["own_theme"] = "custom"
            if self.cfg["shape"] not in OWN_BY_ID:
                self.cfg["shape"] = "EzDrop"
        else:
            self.cfg["bibata_theme"] = "custom"
            if self.cfg["shape"] != "Bibata":
                self.cfg["shape"] = "Bibata"
        self.refresh()

    def pick_bib_color(self):
        res = colorchooser.askcolor(color=self.cfg["color"], parent=self.win, title=T("Chọn màu"))
        if res and res[1]:
            self.set_bib_color(res[1])

    def set_bib(self, key, value):
        self.cfg[key] = value
        if key == "bibata_theme":
            self.cfg["ombre"] = False
        if key == "bibata_theme" and self.cfg["shape"] != "Bibata":
            self.cfg["shape"] = "Bibata"
        self.refresh()

    def add_star(self, tile, fid):
        if not hasattr(self, "star_imgs"):
            self.star_imgs = {True: ctk.CTkImage(star_icon(True, "#FFC940", 32), size=(15, 15)),
                              False: ctk.CTkImage(star_icon(False, "#6B7488", 32), size=(15, 15))}
        sb = ctk.CTkButton(tile, text="", width=24, height=24, corner_radius=7, fg_color="transparent",
                           hover_color="#2A3040", border_width=0, image=self.star_imgs[False],
                           command=lambda: self.toggle_fav(fid))
        sb.place(relx=1.0, x=-5, y=5, anchor="ne")
        self.star_btns[fid] = sb

    def toggle_fav(self, fid):
        favs = list(self.cfg["favorites"])
        if fid in favs:
            favs.remove(fid)
        else:
            favs.append(fid)
        self.cfg["favorites"] = favs
        self.update_library()
        self.save()

    def fav_valid(self, fid):
        if fid.startswith("bib:"):
            return BIBATA_DIR.exists() and fid[4:] in dict(BIBATA_CURSORS)
        if fid.startswith("my:"):
            return (MY_DIR / fid[3:]).is_file()
        return fid in OWN_BY_ID and own_image(fid) is not None

    def fav_label(self, fid):
        if fid.startswith("bib:"):
            return "Bibata · " + T(dict(BIBATA_CURSORS).get(fid[4:], fid[4:]))
        if fid.startswith("my:"):
            return Path(fid[3:]).stem
        return T(OWN_BY_ID[fid][1]) if fid in OWN_BY_ID else T(fid)

    def current_fav_id(self):
        c = self.cfg
        if c["shape"] == "Bibata":
            return "bib:" + c["bibata_cursor"]
        if c["shape"] == "Ảnh tải lên":
            return "my:" + Path(c["image"]).name if c["image"] and Path(c["image"]).parent == MY_DIR else None
        return c["shape"]

    def use_fav(self, fid):
        if not self.fav_valid(fid):
            return
        if fid.startswith("bib:"):
            self.pick_bibata(fid[4:])
        elif fid.startswith("my:"):
            self.use_my_cursor(MY_DIR / fid[3:])
        else:
            self.set_shape(fid)

    def pick_own(self, shape):
        self.cfg["shape"] = shape
        self.refresh()

    def pick_bibata(self, name):
        self.cfg["bibata_cursor"] = name
        self.cfg["shape"] = "Bibata"
        self.refresh()

    def update_library(self):
        self._update_library()
        c = self.cfg
        oimg = ctk.CTkImage(ombre_swatch(c["ombre_colors"], 32), size=(16, 16))
        for b in getattr(self, "ombre_chips", []):
            try:
                self._chip_style(b, c["ombre"], oimg)
            except tk.TclError:
                pass
        for sb in getattr(self, "star_btns", {}).values():
            try:
                col = sb.master.cget("fg_color")
                hov = sb.master.cget("hover_color")
                if getattr(sb, "_bg", None) != col:
                    sb._bg = col
                    sb.configure(fg_color=col, bg_color=col, hover_color=hov)
            except (tk.TclError, ValueError):
                pass

    def _update_library(self):
        if getattr(self, "bib_swatches", None) is None:
            return
        c = self.cfg
        view = self.lib_view
        for key, b in self.own_theme_buttons.items():
            img = (ctk.CTkImage(own_image("EzDrop").resize((32, 32), Image.LANCZOS), size=(16, 16))
                   if key == "original" and own_image("EzDrop") is not None else self._chip_dot(c["color"]))
            self._chip_style(b, key == c["own_theme"] and not c["ombre"], img)
        for key, b in self.theme_buttons.items():
            col = BIBATA_THEMES[key][1] if key in BIBATA_THEMES else c["color"]
            self._chip_style(b, key == c["bibata_theme"] and not c["ombre"], self._chip_dot(col))
        for key, b in getattr(self, "mine_theme_buttons", {}).items():
            img = (self._chip_dot(c["color"]) if key == "tint" or own_image("EzDrop") is None
                   else ctk.CTkImage(own_image("EzDrop").resize((32, 32), Image.LANCZOS), size=(16, 16)))
            self._chip_style(b, (key == "tint") == bool(c["tint_image"]) and not c["ombre"], img)
        favs = set(c["favorites"])
        for fid, sb in getattr(self, "star_btns", {}).items():
            on = fid in favs
            if getattr(sb, "_fav_on", None) != on:
                sb._fav_on = on
                try:
                    sb.configure(image=self.star_imgs[on])
                except tk.TclError:
                    pass
        mine_sel = c["image"] if c["shape"] == "Ảnh tải lên" else None
        for path, b in getattr(self, "mine_tiles", {}).items():
            on = path == mine_sel
            b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)
        for cid, b in getattr(self, "cat_tiles", {}).items():
            f = self.cat_file(cid)
            on = mine_sel is not None and f is not None and Path(mine_sel) == f
            try:
                b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                            hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                            border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)
            except tk.TclError:
                pass
        if getattr(self, "mine_del", None):
            self.mine_del.configure(state="normal" if mine_sel and mine_sel in self.mine_tiles else "disabled")
            made = mine_sel and mine_sel in self.mine_tiles and Path(mine_sel).name in c["made_cursors"]
            self.mine_edit.configure(state="normal" if made else "disabled")
        custom_on = {"ez": c["own_theme"] == "custom", "bibata": c["bibata_theme"] == "custom",
                     "mine": bool(c["tint_image"])}.get(view, False) and not c["ombre"]
        known = set()
        for col, b in self.bib_swatches.items():
            known.add(col.lower())
            on = custom_on and col.lower() == c["color"].lower()
            plain = col in ("#FFFFFF", "#000000")
            b.configure(border_width=3 if on else (1 if plain else 0),
                        border_color=ACCENT if (on and col == "#FFFFFF") else ("#FFFFFF" if on else "#4A5266"))
        if custom_on and c["color"].lower() not in known:
            self.bib_custom_btn.configure(fg_color=c["color"], hover_color=c["color"], border_width=3,
                                          border_color="#FFFFFF", image=None)
        else:
            self.bib_custom_btn.configure(fg_color="transparent", hover_color="#1A1E29", border_width=1,
                                          border_color="#4A5266",
                                          image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(14, 14)))
        # hình trên ô: chỉ vẽ lại khi đổi chủ đề / màu
        oc = tuple(c["ombre_colors"]) if c["ombre"] else None
        osig = (c["own_theme"], c["color"].lower() if c["own_theme"] == "custom" else "", oc)
        if osig != self._own_sig:
            self._own_sig = osig
            for shape, b in self.own_tiles.items():
                if oc:
                    im = own_image(shape).resize((112, 112), Image.LANCZOS)
                    hx, hy = OWN_BY_ID[shape][3]
                    im = apply_ombre(im, ombre_tmap(im, (hx * 112 // 256, hy * 112 // 256)), ombre_lut(oc))
                else:
                    im = own_image_colored(shape, c["color"]) if c["own_theme"] == "custom" else own_image(shape)
                    im = im.resize((112, 112), Image.LANCZOS)
                b.configure(image=ctk.CTkImage(im, size=(56, 56)))
        if self.bib_tiles:
            variant = self.bibata_variant()
            colors = bibata_colors("custom" if oc else c["bibata_theme"], oc[0] if oc else c["color"])
            sig = (variant, colors, oc)
            if sig != self._lib_sig:
                self._lib_sig = sig
                for name, b in self.bib_tiles.items():
                    im = bibata_image(BIBATA_DIR, variant, name, colors).resize((112, 112), Image.LANCZOS)
                    if oc:
                        hx, hy = BIBATA_META["hotspots"].get(f"{variant}/{name}", [128, 128])
                        im = apply_ombre(im, ombre_tmap(im, (hx * 112 // 256, hy * 112 // 256)), ombre_lut(oc))
                    b.configure(image=ctk.CTkImage(im, size=(56, 56)))
        tile_bg = mix(FIELD, "#FFFFFF", 0.05) if c["bibata_theme"] == "classic" else FIELD
        for shape, tile in self.own_tiles.items():
            on = c["shape"] == shape
            tile.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                           hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                           border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT)
        for name, b in self.bib_tiles.items():
            on = c["shape"] == "Bibata" and name == c["bibata_cursor"]
            b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else tile_bg,
                        hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                        border_color=ACCENT if on else BORDER, text_color="#FFFFFF" if on else TEXT2)

"""Thiết lập lần đầu."""

import tkinter as tk

import customtkinter as ctk
from PIL import Image

from ..base import APP_NAME
from ..system import list_running_apps
from ..i18n import T
from ..hotkeys import hotkey_parts
from ..config import ARPG_GAMES
from ..colors import mix
from ..theme import ACCENT, BG, BORDER, CARD, CYAN, CYAN_TEXT, FIELD, MUTED, TEXT, TEXT2
from ..bibata import OWN_BY_ID, OWN_CURSORS, own_image


class WizardMixin:
    def wait_setup(self):
        """Chờ tới khi cửa sổ chính hiện (sau màn hình chào / khi mở từ khay) rồi mới mở thiết lập."""
        if self.quitting or getattr(self, "setup_win", None) is not None:
            return
        try:
            ready = self.win.winfo_viewable() and not getattr(self, "splashing", False)
        except (tk.TclError, AttributeError):
            ready = False
        if ready:
            self.run_setup()
        else:
            self.ov.after(400, self.wait_setup)

    def run_setup(self):
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        self.setup_win = d
        d.title(APP_NAME)
        d.resizable(False, False)
        d.transient(self.win)
        d.attributes("-topmost", True)
        running = {n.lower() for n, _ in list_running_apps()}
        app_set = {a.lower() for a in self.cfg["apps"]}
        st = {"step": 0, "shape": self.cfg["shape"] if self.cfg["shape"] in OWN_BY_ID else "EzDrop",
              "size": self.cfg["size"]}
        game_vars = [(tk.BooleanVar(value=any(e.lower() in running or e.lower() in app_set for e in exes)), title, exes)
                     for title, exes in ARPG_GAMES]
        all_var = tk.BooleanVar(value=self.cfg["all_apps"])

        outer = ctk.CTkFrame(d, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=(20, 18))
        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x")
        self.caps(top, "THIẾT LẬP NHANH", ACCENT).pack(side="left")
        step_lbl = ctk.CTkLabel(top, text="", font=self.F.m(11), text_color=MUTED)
        step_lbl.pack(side="right")
        bar = ctk.CTkFrame(outer, fg_color="transparent")
        bar.pack(fill="x", pady=(8, 14))
        dots = []
        for i in range(3):
            seg = ctk.CTkFrame(bar, height=4, corner_radius=2, fg_color=BORDER)
            seg.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 6, 0))
            dots.append(seg)
        body = ctk.CTkFrame(outer, fg_color="transparent", width=640, height=380)
        body.pack(fill="both", expand=True)
        body.pack_propagate(False)
        foot = ctk.CTkFrame(outer, fg_color="transparent")
        foot.pack(fill="x", pady=(14, 0))
        skip = ctk.CTkButton(foot, text=T("Bỏ qua"), width=90, height=40, fg_color="transparent",
                             hover_color="#1A1E29", text_color=TEXT2, font=self.F.b(13), command=lambda: finish(False))
        skip.pack(side="left")
        nxt = ctk.CTkButton(foot, text="", width=150, height=42, corner_radius=10, fg_color=ACCENT,
                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF", font=self.F.h(15),
                            command=lambda: go(1))
        nxt.pack(side="right")
        back = ctk.CTkButton(foot, text=T("Quay lại"), width=110, height=42, corner_radius=10, border_width=1,
                             border_color=BORDER, fg_color="transparent", hover_color="#1A1E29", text_color=TEXT,
                             font=self.F.b(13, strong=True), command=lambda: go(-1))

        def title(parent, t, sub):
            ctk.CTkLabel(parent, text=T(t), font=self.F.h(24), text_color=TEXT).pack(anchor="w")
            ctk.CTkLabel(parent, text=T(sub), font=self.F.b(13), text_color=TEXT2, wraplength=620,
                         justify="left").pack(anchor="w", pady=(2, 14))

        def page_games(f):
            title(f, "Bạn chơi game nào?", "EzCursor chỉ hiện con trỏ khi các game này đang mở. "
                                           "Có thể đổi sau ở tab Ứng dụng.")
            grid = ctk.CTkFrame(f, fg_color="transparent")
            grid.pack(fill="x")
            grid.grid_columnconfigure((0, 1), weight=1, uniform="g")
            for i, (var, name, exes) in enumerate(game_vars):
                cell = ctk.CTkFrame(grid, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=10,
                                    height=44)
                cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 5, 0 if i % 2 else 5),
                          pady=4)
                cb = ctk.CTkCheckBox(cell, text=name, variable=var, font=self.F.b(13, strong=True), text_color=TEXT,
                                     checkbox_width=20, checkbox_height=20, corner_radius=6, border_width=1,
                                     fg_color=ACCENT, hover_color=ACCENT, border_color="#4A5266",
                                     checkmark_color="#FFFFFF")
                cb.pack(side="left", padx=12, pady=10)
                if any(e.lower() in running for e in exes):
                    ctk.CTkLabel(cell, text=T(" ĐANG CHẠY "), font=self.F.m(10), text_color=CYAN_TEXT,
                                 corner_radius=10, height=20, fg_color=mix(CARD, CYAN, 0.1)).pack(side="right", padx=10)
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=(14, 0))
            self.switch(row, all_var, lambda: None).pack(side="left")
            ctk.CTkLabel(row, text=T("  Áp dụng cho mọi ứng dụng (kể cả Desktop)"), font=self.F.b(13),
                         text_color=TEXT).pack(side="left")

        def page_cursor(f):
            title(f, "Chọn con trỏ", "Chọn con trỏ bạn thích. Bộ sưu tập còn bộ Bibata và chỗ thêm con trỏ "
                                     "của riêng bạn.")
            grid = ctk.CTkFrame(f, fg_color="transparent")
            grid.pack(fill="x")
            cols = 7
            for i in range(cols):
                grid.grid_columnconfigure(i, weight=1, uniform="c")
            tiles = {}
            name_lbl = ctk.CTkLabel(f, text="", font=self.F.b(14, strong=True), text_color=TEXT)

            def paint():
                name_lbl.configure(text=T(OWN_BY_ID[st["shape"]][1]))
                for sh, b in tiles.items():
                    on = sh == st["shape"]
                    b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD,
                                hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                                border_color=ACCENT if on else BORDER)

            def pick(sh):
                st["shape"] = sh
                paint()

            n = 0
            for sh, label, _f, _h, _g in OWN_CURSORS:
                im = own_image(sh)
                if im is None:
                    continue
                b = ctk.CTkButton(grid, text="", width=10, height=78, corner_radius=12, border_width=1,
                                  image=ctk.CTkImage(im.resize((104, 104), Image.LANCZOS), size=(52, 52)),
                                  command=lambda sh=sh: pick(sh))
                b.grid(row=n // cols, column=n % cols, sticky="ew", padx=3, pady=3)
                tiles[sh] = b
                n += 1
            paint()
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=(16, 0))
            self.caps(row, "KÍCH THƯỚC").pack(side="left", padx=(0, 12))
            sizes = {T("Nhỏ"): 48, T("Vừa"): 64, T("Lớn"): 88}
            seg = ctk.CTkSegmentedButton(row, values=list(sizes), height=36, font=self.F.b(13, strong=True),
                                         fg_color=FIELD, unselected_color=FIELD, unselected_hover_color="#1A1E29",
                                         selected_color=mix(CARD, ACCENT, 0.35),
                                         selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT,
                                         command=lambda v: st.update(size=sizes[v]))
            seg.pack(side="left")
            name_lbl.pack(in_=row, side="right")
            name_lbl.lift()
            seg.set(min(sizes, key=lambda k: abs(sizes[k] - st["size"])))
            st["size"] = sizes[seg.get()]

        def page_done(f):
            title(f, "Sẵn sàng!", "Mở game là con trỏ mới sẽ hiện. Vài phím tắt nên nhớ:")
            games = [name for var, name, _ in game_vars if var.get()]
            card = self.card(f)
            card.pack(fill="x")
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=12)
            sh = st["shape"]
            line = ctk.CTkFrame(inner, fg_color="transparent")
            line.pack(fill="x", pady=(0, 8))
            if own_image(sh) is not None:
                ctk.CTkLabel(line, text="", image=ctk.CTkImage(own_image(sh).resize((80, 80), Image.LANCZOS),
                                                               size=(40, 40))).pack(side="left", padx=(0, 12))
            txt = ctk.CTkFrame(line, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(txt, text=T(OWN_BY_ID[sh][1]), font=self.F.b(15, strong=True), text_color=TEXT,
                         anchor="w").pack(anchor="w")
            where = T("Mọi ứng dụng") if all_var.get() else (", ".join(games) or T("(chưa chọn)"))
            ctk.CTkLabel(txt, text=T("Game") + ": " + where, font=self.F.b(12), text_color=TEXT2, anchor="w",
                         wraplength=520, justify="left").pack(anchor="w")
            hk = self.cfg["hotkeys"]
            for act, label in (("toggle", "Bật / tắt"), ("shape", "Đổi con trỏ (giữa các con trỏ yêu thích)"),
                               ("find", "Tìm con trỏ (hoặc lắc chuột)"), ("color", "Đổi màu")):
                r = ctk.CTkFrame(inner, fg_color="transparent")
                r.pack(fill="x", pady=2)
                ctk.CTkLabel(r, text=" + ".join(hotkey_parts(hk[act], act)), font=self.F.m(12), text_color=ACCENT,
                             width=150, anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=T(label), font=self.F.b(13), text_color=TEXT, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=T("EzCursor chạy ở khay hệ thống. Chuột phải vào icon để đổi nhanh con trỏ "
                                   "hoặc hồ sơ."), font=self.F.b(12), text_color=TEXT2, wraplength=620,
                         justify="left").pack(anchor="w", pady=(12, 0))

        pages = [page_games, page_cursor, page_done]

        def show():
            for w in body.winfo_children():
                w.destroy()
            f = ctk.CTkFrame(body, fg_color="transparent")
            f.pack(fill="both", expand=True)
            pages[st["step"]](f)
            i = st["step"]
            step_lbl.configure(text=T("Bước {i} / 3").format(i=i + 1))
            for k, seg in enumerate(dots):
                seg.configure(fg_color=ACCENT if k <= i else BORDER)
            nxt.configure(text=T("Bắt đầu") if i == 2 else T("Tiếp tục"))
            if i > 0:
                if not back.winfo_ismapped():
                    back.pack(side="right", padx=(0, 8))
            else:
                back.pack_forget()

        def go(delta):
            if st["step"] == 2 and delta > 0:
                finish(True)
                return
            st["step"] = max(0, min(2, st["step"] + delta))
            show()

        def finish(apply):
            if apply:
                apps = list(self.cfg["apps"])
                low = {a.lower() for a in apps}
                for var, _name, exes in game_vars:
                    for e in exes:
                        if var.get() and e.lower() not in low:
                            apps.append(e)
                            low.add(e.lower())
                        elif not var.get() and e.lower() in low:
                            apps = [a for a in apps if a.lower() != e.lower()]
                            low.discard(e.lower())
                self.cfg["apps"] = apps
                self.cfg["all_apps"] = bool(all_var.get())
                base = self.cfg.base
                base["shape"], base["size"] = st["shape"], st["size"]
                self.update_app_set()
                try:
                    self.all_var.set(self.cfg["all_apps"])
                    self.update_applied_label()
                except AttributeError:
                    pass
                self.refresh_apps()
                if self.cfg.target is base:
                    self.sync_style_widgets()
                self.refresh()
            self.cfg["setup_done"] = True
            self.save()
            self.setup_win = None
            try:
                d.destroy()
            except tk.TclError:
                pass
            self.show_tab("cursor")

        d.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        show()
        try:
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 3
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)
        d.after(250, lambda: d.grab_set() if d.winfo_exists() else None)

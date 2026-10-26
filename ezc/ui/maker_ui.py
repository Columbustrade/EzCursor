"""Cửa sổ Trình tạo con trỏ."""

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from ..base import MY_DIR
from ..i18n import T
from ..config import unique_my_path
from ..colors import mix
from ..ombre import OMBRE_PRESETS, ombre_dot
from ..maker import MAKER_DEFAULT, MAKER_SHAPES, MAKER_SHAPE_DEFAULTS, maker_render, png_to_cur
from ..theme import ACCENT, BG, BORDER, CARD, CYAN, FIELD, MUTED, SWATCHES, TEXT, TEXT2
from ..icons import simple_icon


class MakerMixin:
    def edit_made_cursor(self):
        img = self.cfg["image"]
        if self.cfg["shape"] == "Ảnh tải lên" and img:
            spec = self.cfg["made_cursors"].get(Path(img).name)
            if spec:
                self.open_maker(spec, Path(img))

    def open_maker(self, spec=None, path=None):
        if getattr(self, "maker_win", None) is not None:
            try:
                self.maker_win.lift()
                return
            except tk.TclError:
                pass
        sp = dict(MAKER_DEFAULT, **(spec or {}))
        sp["ombre"] = list(sp["ombre"])
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        self.maker_win = d
        d.title(T("Tạo con trỏ"))
        d.resizable(False, False)
        d.transient(self.win)
        state = {"job": None, "img": None, "hot": (0, 0)}
        PV = 300

        outer = ctk.CTkFrame(d, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(outer, text=T("TẠO CON TRỎ"), font=self.F.h(22), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(outer, text=T("Chọn hình, chỉnh dáng, màu và viền. Con trỏ được lưu vào mục Của bạn."),
                     font=self.F.b(13), text_color=TEXT2).pack(anchor="w", pady=(0, 12))
        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # --- bên trái: xem trước
        left = self.card(body)
        left.pack(side="left", fill="y", padx=(0, 14))
        cv = tk.Canvas(left, width=PV, height=PV, bg=FIELD, highlightthickness=1, highlightbackground=BORDER,
                       bd=0, cursor="crosshair")
        cv.pack(padx=14, pady=(14, 6))
        for i in range(0, PV, 20):
            cv.create_line(i, 0, i, PV, fill="#151A24")
            cv.create_line(0, i, PV, i, fill="#151A24")
        img_id = cv.create_image(PV // 2, PV // 2)
        hot_ids = [cv.create_line(0, 0, 0, 0, fill=CYAN, width=1) for _ in range(2)]
        ctk.CTkLabel(left, text=T("Bấm vào hình để đặt điểm click"), font=self.F.b(12),
                     text_color=MUTED).pack()
        ctk.CTkButton(left, text=T("Điểm click tự động"), height=28, width=10, corner_radius=8, border_width=1,
                      border_color=BORDER, fg_color="transparent", hover_color="#1A1E29", text_color=TEXT2,
                      font=self.F.b(12), command=lambda: (sp.update(hot=None), redraw())).pack(pady=(4, 8))
        small = tk.Canvas(left, width=PV, height=86, bg=CARD, highlightthickness=0, bd=0)
        small.pack(padx=14, pady=(0, 14))
        small.create_rectangle(PV // 2, 4, PV - 2, 84, fill="#C9BFA8", outline="")
        small.create_rectangle(2, 4, PV // 2, 84, fill="#10141C", outline="")
        small_ids = [small.create_image(x, 44) for x in (40, 105, 190, 255)]
        self.caps(left, "KÍCH THƯỚC THẬT").place(x=16, y=PV + 74)

        # --- bên phải: tùy chọn
        right = ctk.CTkScrollableFrame(body, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=14,
                                       width=470, height=PV + 150, scrollbar_button_color=BORDER,
                                       scrollbar_button_hover_color="#3A4152")
        right.pack(side="left", fill="both", expand=True)
        pad = dict(padx=14)

        self.caps(right, "HÌNH DÁNG").pack(anchor="w", pady=(12, 6), **pad)
        sg = ctk.CTkFrame(right, fg_color="transparent")
        sg.pack(fill="x", **pad)
        for i in range(5):
            sg.grid_columnconfigure(i, weight=1, uniform="m")
        shape_btns = {}
        for i, (key, name, _kind) in enumerate(MAKER_SHAPES):
            th = maker_render(dict(MAKER_SHAPE_DEFAULTS[key], shape=key, color="#C9CFDC", in_w=0, out_w=0,
                                   shadow=False, shine=False, tip=False), 72)[0]
            b = ctk.CTkButton(sg, text=T(name), compound="top", height=70, width=10, corner_radius=10,
                              border_width=1, font=self.F.b(11), image=ctk.CTkImage(th, size=(32, 32)),
                              command=lambda k=key: set_shape(k))
            b.grid(row=i // 5, column=i % 5, sticky="ew", padx=3, pady=3)
            shape_btns[key] = b

        def slider(label, key, lo, hi, steps):
            row = ctk.CTkFrame(right, fg_color="transparent")
            lab = ctk.CTkLabel(row, text=T(label), font=self.F.b(13), text_color=TEXT, width=110, anchor="w")
            lab.pack(side="left")
            sl = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=steps, progress_color=ACCENT,
                               button_color=ACCENT, button_hover_color=mix(ACCENT, "#FFFFFF", 0.25),
                               fg_color="#1A1E29", height=16, command=lambda v, k=key: (sp.update({k: v}), redraw()))
            sl.pack(side="left", fill="x", expand=True)
            sl.set(sp[key])
            return row, lab, sl

        self.caps(right, "DÁNG").pack(anchor="w", pady=(14, 4), **pad)
        sliders = {
            "width": slider("Độ rộng", "width", 0.4, 1.6, 60),
            "tail": slider("Độ dài đuôi", "tail", 0.0, 1.0, 50),
            "thick": slider("Độ dày nét", "thick", 0.0, 1.0, 50),
            "round": slider("Bo góc", "round", 0.0, 1.0, 50),
            "rot": slider("Xoay", "rot", -60, 60, 120),
        }

        self.caps(right, "TÔ MÀU").pack(anchor="w", pady=(14, 6), **pad)
        fill_map = {T("Một màu"): "solid", "Ombre": "ombre", T("Kính mờ"): "glass"}
        fill_seg = ctk.CTkSegmentedButton(right, values=list(fill_map), height=32, font=self.F.b(12, strong=True),
                                          fg_color=FIELD, unselected_color=FIELD, unselected_hover_color="#1A1E29",
                                          selected_color=mix(CARD, ACCENT, 0.35),
                                          selected_hover_color=mix(CARD, ACCENT, 0.45), text_color=TEXT,
                                          command=lambda v: (sp.update(fill=fill_map[v]), redraw()))
        fill_seg.pack(anchor="w", **pad)
        fill_seg.set({v: k for k, v in fill_map.items()}[sp["fill"]])
        color_row = ctk.CTkFrame(right, fg_color="transparent")
        color_row.pack(fill="x", pady=(8, 0), **pad)
        sw_btns = {}
        for c, _n in SWATCHES:
            b = ctk.CTkButton(color_row, text="", width=28, height=28, corner_radius=14, fg_color=c,
                              hover_color=mix(c, "#FFFFFF", 0.2), border_width=0,
                              command=lambda c=c: (sp.update(color=c), redraw()))
            b.pack(side="left", padx=(0, 6))
            sw_btns[c] = b

        def pick_main():
            res = colorchooser.askcolor(color=sp["color"], parent=d, title=T("Chọn màu"))
            if res and res[1]:
                sp["color"] = res[1].upper()
                redraw()

        ctk.CTkButton(color_row, text="", width=28, height=28, corner_radius=14, fg_color="transparent",
                      hover_color="#1A1E29", border_width=1, border_color="#4A5266",
                      image=ctk.CTkImage(simple_icon("plus", TEXT2, 32), size=(12, 12)),
                      command=pick_main).pack(side="left")
        ombre_row = ctk.CTkFrame(right, fg_color="transparent")
        ombre_row.pack(fill="x", pady=(8, 0), **pad)
        ombre_lbls = {}
        for key, _n, cols in OMBRE_PRESETS:
            lb = ctk.CTkLabel(ombre_row, text="", width=28, height=28, cursor="hand2",
                              image=ctk.CTkImage(ombre_dot(cols, False), size=(28, 28)))
            lb.bind("<Button-1>", lambda e, cl=cols: (sp.update(ombre=list(cl), fill="ombre"), redraw()))
            lb.pack(side="left", padx=(0, 6))
            ombre_lbls[key] = lb

        self.caps(right, "VIỀN").pack(anchor="w", pady=(14, 4), **pad)
        edge_btns = {}

        def edge_row(label, ckey, wkey):
            row = ctk.CTkFrame(right, fg_color="transparent")
            row.pack(fill="x", pady=3, **pad)
            ctk.CTkLabel(row, text=T(label), font=self.F.b(13), text_color=TEXT, width=110,
                         anchor="w").pack(side="left")

            def pick():
                res = colorchooser.askcolor(color=sp[ckey], parent=d, title=T("Chọn màu"))
                if res and res[1]:
                    sp[ckey] = res[1].upper()
                    redraw()

            b = ctk.CTkButton(row, text="", width=28, height=28, corner_radius=14, border_width=2,
                              border_color="#4A5266", command=pick)
            b.pack(side="left", padx=(0, 10))
            edge_btns[ckey] = b
            sl = ctk.CTkSlider(row, from_=0, to=14, number_of_steps=14, progress_color=ACCENT, button_color=ACCENT,
                               button_hover_color=mix(ACCENT, "#FFFFFF", 0.25), fg_color="#1A1E29", height=16,
                               command=lambda v: (sp.update({wkey: int(v)}), redraw()))
            sl.pack(side="left", fill="x", expand=True)
            sl.set(sp[wkey])

        edge_row("Viền trong", "in_col", "in_w")
        edge_row("Viền ngoài", "out_col", "out_w")

        self.caps(right, "CHI TIẾT").pack(anchor="w", pady=(14, 4), **pad)
        det = ctk.CTkFrame(right, fg_color="transparent")
        det.pack(fill="x", pady=(0, 14), **pad)
        for key, label in (("tip", "Chấm sáng ở mũi"), ("shine", "Vệt sáng"), ("shadow", "Bóng đổ")):
            var = tk.BooleanVar(value=sp[key])
            ctk.CTkCheckBox(det, text=T(label), variable=var, font=self.F.b(13), text_color=TEXT, checkbox_width=20,
                            checkbox_height=20, corner_radius=6, border_width=1, fg_color=ACCENT, hover_color=ACCENT,
                            border_color="#4A5266", checkmark_color="#FFFFFF",
                            command=lambda k=key, v=var: (sp.update({k: bool(v.get())}), redraw())
                            ).pack(side="left", padx=(0, 16))

        # --- dưới cùng: tên + lưu
        foot = ctk.CTkFrame(outer, fg_color="transparent")
        foot.pack(fill="x", pady=(14, 0))
        ctk.CTkLabel(foot, text=T("Tên"), font=self.F.b(13), text_color=TEXT2).pack(side="left", padx=(0, 8))
        name_var = tk.StringVar(value=path.stem if path else T("Con trỏ của tôi"))
        ctk.CTkEntry(foot, textvariable=name_var, width=240, height=38, corner_radius=10, border_color=BORDER,
                     fg_color=FIELD, text_color=TEXT, font=self.F.b(13)).pack(side="left")

        def close():
            self.maker_win = None
            try:
                d.destroy()
            except tk.TclError:
                pass

        def save():
            im, hot = maker_render(sp)
            data = png_to_cur(im, hot)
            try:
                MY_DIR.mkdir(parents=True, exist_ok=True)
                name = name_var.get().strip() or T("Con trỏ của tôi")
                dest = path if path is not None and Path(path).exists() else unique_my_path(name + ".cur")
                Path(dest).write_bytes(data)
            except OSError as e:
                messagebox.showerror(T("Lỗi"), T("Không lưu được con trỏ:") + f"\n{e}", parent=d)
                return
            keep = {k: sp[k] for k in MAKER_DEFAULT}
            self.cfg["made_cursors"] = dict(self.cfg["made_cursors"], **{Path(dest).name: keep})
            self.img_cache.clear()
            close()
            self.rebuild_mine_tiles()
            self.cfg["tint_image"] = False          # con trỏ tự tạo giữ đúng màu đã chọn
            self.cfg["ombre"] = False
            try:
                self.tint_var.set(False)
            except AttributeError:
                pass
            self.use_my_cursor(dest)
            self.save()

        ctk.CTkButton(foot, text=T("Lưu vào Của bạn"), command=save, height=42, width=170, corner_radius=10,
                      fg_color=ACCENT, hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF",
                      font=self.F.h(14)).pack(side="right")
        ctk.CTkButton(foot, text=T("Hủy"), command=close, width=90, height=42, corner_radius=10,
                      fg_color="transparent", hover_color="#1A1E29", text_color=TEXT2,
                      font=self.F.b(13)).pack(side="right", padx=(0, 8))

        # --- vẽ lại
        def set_shape(key):
            sp.update(MAKER_SHAPE_DEFAULTS[key], shape=key, hot=None)
            for k, (_row, _lab, sl) in sliders.items():
                sl.set(sp[k])
            redraw()

        def render_now():
            state["job"] = None
            try:
                im, hot = maker_render(sp)
            except Exception:
                self.report_error("maker", once=True)
                return
            state["img"], state["hot"] = im, hot
            S = 240
            ph = ImageTk.PhotoImage(im.resize((S, S), Image.LANCZOS), master=self.ov)
            cv.itemconfig(img_id, image=ph)
            cv._ph = ph
            off = (PV - S) // 2
            hx, hy = off + hot[0] * S / 256, off + hot[1] * S / 256
            cv.coords(hot_ids[0], hx - 9, hy, hx + 10, hy)
            cv.coords(hot_ids[1], hx, hy - 9, hx, hy + 10)
            phs = []
            for idx, size in enumerate((32, 48, 32, 48)):
                p2 = ImageTk.PhotoImage(im.resize((size, size), Image.LANCZOS), master=self.ov)
                small.itemconfig(small_ids[idx], image=p2)
                phs.append(p2)
            small._ph = phs
            # trạng thái các nút
            kind = dict((a, c) for a, _, c in MAKER_SHAPES)[sp["shape"]]
            for k, b in shape_btns.items():
                on = k == sp["shape"]
                b.configure(fg_color=mix(CARD, ACCENT, 0.16) if on else FIELD, border_color=ACCENT if on else BORDER,
                            hover_color=mix(CARD, ACCENT, 0.24) if on else "#161A23",
                            text_color="#FFFFFF" if on else TEXT2)
            show = {"width": True, "rot": sp["shape"] not in ("dot", "ring"),
                    "tail": kind == "poly" or sp["shape"] == "cross",
                    "thick": sp["shape"] in ("ring", "cross"), "round": kind == "poly"}
            want = [k for k in sliders if show[k]]
            if want != state.get("rows"):
                state["rows"] = want
                for k, (row, _lab, _sl) in sliders.items():
                    row.pack_forget()
                for k in want:
                    sliders[k][0].pack(fill="x", pady=3, padx=14, before=sliders_anchor)
            sliders["tail"][1].configure(text=T("Khe hở") if sp["shape"] == "cross" else T("Độ dài đuôi"))
            for c, b in sw_btns.items():
                on = sp["fill"] != "ombre" and c.lower() == sp["color"].lower()
                b.configure(border_width=3 if on else 0, border_color="#FFFFFF")
            cur = [x.lower() for x in sp["ombre"]]
            for key, _n, cols in OMBRE_PRESETS:
                on = sp["fill"] == "ombre" and [x.lower() for x in cols] == cur
                ombre_lbls[key].configure(image=ctk.CTkImage(ombre_dot(cols, on), size=(28, 28)))
            for ckey, b in edge_btns.items():
                b.configure(fg_color=sp[ckey], hover_color=sp[ckey])
            fill_seg.set({v: k for k, v in fill_map.items()}[sp["fill"]])

        def redraw():
            if state["job"] is None:
                state["job"] = d.after(40, render_now)

        def on_click(e):
            S = 240
            off = (PV - S) // 2
            x, y = (e.x - off) * 256 / S, (e.y - off) * 256 / S
            if 0 <= x < 256 and 0 <= y < 256:
                sp["hot"] = [int(x), int(y)]
                redraw()

        cv.bind("<Button-1>", on_click)
        # các hàng thanh trượt nằm trước nhãn TÔ MÀU
        sliders_anchor = [w for w in right.winfo_children() if isinstance(w, ctk.CTkLabel)
                          and w.cget("text") == T("TÔ MÀU")][0]
        d.protocol("WM_DELETE_WINDOW", close)
        render_now()
        try:
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 4
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)

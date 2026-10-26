"""Tab Ứng dụng: chọn game / ứng dụng được áp dụng con trỏ."""

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from ..system import _name_cache, list_running_apps
from ..i18n import T
from ..config import ARPG_GAMES
from ..colors import mix
from ..theme import ACCENT, BORDER, CARD, CYAN, CYAN_TEXT, GREEN, MUTED, TEXT, TEXT2
from ..icons import simple_icon


class AppsMixin:
    def build_apps_tab(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        self.header(top, "ỨNG DỤNG", "Chọn game sẽ dùng con trỏ của EzCursor, rồi bấm Áp dụng.").pack(side="left")
        self.cyan_button(top, "Làm mới", self.refresh_apps,
                         ctk.CTkImage(simple_icon("refresh", CYAN_TEXT, 32), size=(16, 16))).pack(side="right", anchor="s")

        self.app_list = ctk.CTkScrollableFrame(page, fg_color=CARD, border_color=BORDER, border_width=1,
                                               corner_radius=14, height=int(390), scrollbar_button_color=BORDER,
                                               scrollbar_button_hover_color="#3A4152")
        self.app_list.pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(page, fg_color="transparent")
        bottom.pack(fill="x", pady=(14, 0))
        self.all_var = tk.BooleanVar(value=self.cfg["all_apps"])
        self.switch(bottom, self.all_var, self.set_all_apps).pack(side="left")
        ctk.CTkLabel(bottom, text=T("  Áp dụng cho mọi ứng dụng (kể cả Desktop)"), font=self.F.b(13),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(bottom, text=T("ÁP DỤNG"), command=self.apply_apps, height=44, width=150, corner_radius=10,
                      fg_color=ACCENT, hover_color=mix(ACCENT, "#FFFFFF", 0.15), text_color="#FFFFFF",
                      font=self.F.h(15)).pack(side="right")
        self.applied_label = ctk.CTkLabel(page, text="", font=self.F.b(12), text_color=TEXT2, anchor="w",
                                          justify="left", wraplength=680)
        self.applied_label.pack(fill="x", pady=(10, 0))
        self.update_applied_label()
        return page

    def refresh_apps(self):
        _name_cache.clear()
        running = list_running_apps()
        running_names = {n.lower() for n, _ in running}
        # (khóa, tiêu đề, dòng phụ, các file chạy, trạng thái)
        items = [(n, t, n, [n], "run") for n, t in running]
        preset_of = {exe.lower(): (title, exes) for title, exes in ARPG_GAMES for exe in exes}
        shown_presets = set()
        for n in self.cfg["apps"]:
            if n.lower() in running_names:
                continue
            pre = preset_of.get(n.lower())
            if pre and not any(e.lower() in running_names for e in pre[1]):
                if pre[0] not in shown_presets:
                    shown_presets.add(pre[0])
                    items.append(("preset:" + pre[0], pre[0], ", ".join(pre[1]), pre[1], "off"))
            else:
                items.append((n, T("(đang không chạy)"), n, [n], "off"))
        suggest = [("preset:" + title, title, ", ".join(exes), exes, "hint") for title, exes in ARPG_GAMES
                   if title not in shown_presets and not any(e.lower() in running_names for e in exes)]
        old = {k: v[0].get() for k, v in self.app_vars.items()}
        for w in self.app_list.winfo_children():
            w.destroy()
        self.app_vars = {}
        for i, (key, title, sub, exes, state) in enumerate(items + suggest):
            if i == len(items) and suggest:
                self.caps(self.app_list, "GỢI Ý: GAME ARPG PHỔ BIẾN").pack(anchor="w", padx=12, pady=(12, 4))
            checked = old.get(key, any(e.lower() in self.app_set for e in exes))
            var = tk.BooleanVar(value=checked)
            self.app_vars[key] = (var, exes)
            pname = title if key.startswith("preset:") else Path(exes[0]).stem
            self.add_app_row(sub, title, state, var, exes, pname)

    def add_app_row(self, name, title, running, var, exes=(), pname=""):
        row = ctk.CTkFrame(self.app_list, corner_radius=10, border_width=1, height=54)
        row.pack(fill="x", padx=6, pady=3)
        cb = ctk.CTkCheckBox(row, text="", variable=var, width=24, checkbox_width=20, checkbox_height=20,
                             corner_radius=6, border_width=1, fg_color=ACCENT, hover_color=ACCENT,
                             border_color="#4A5266", checkmark_color="#FFFFFF")
        cb.pack(side="left", padx=(12, 6), pady=10)
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        t = title if len(title) <= 50 else title[:47] + "..."
        l1 = ctk.CTkLabel(txt, text=t, font=self.F.b(14, strong=True), text_color=TEXT, height=20, anchor="w")
        l1.pack(anchor="w")
        sub = name if len(name) <= 70 else name[:67] + "..."
        l2 = ctk.CTkLabel(txt, text=sub, font=self.F.m(12), text_color=MUTED, height=16, anchor="w")
        l2.pack(anchor="w")
        badge_txt, badge_col, badge_bg = {
            "run": (T(" ĐANG CHẠY "), CYAN_TEXT, mix(CARD, CYAN, 0.1)),
            "hint": (T(" GỢI Ý "), GREEN, mix(CARD, GREEN, 0.1)),
        }.get(running, (T(" KHÔNG CHẠY "), MUTED, "#181C26"))
        badge = ctk.CTkLabel(row, text=badge_txt, font=self.F.m(10), text_color=badge_col, corner_radius=11,
                             height=22, fg_color=badge_bg)
        badge.pack(side="right", padx=12, before=txt)
        has = any(self.profile_for_exe(e) for e in exes)
        prof = ctk.CTkButton(row, text=T("✓ Hồ sơ riêng") if has else T("+ Hồ sơ riêng"), width=10, height=26,
                             corner_radius=8, font=self.F.b(12, strong=has), border_width=1,
                             border_color=ACCENT if has else BORDER,
                             fg_color=mix(CARD, ACCENT, 0.18) if has else "transparent",
                             hover_color=mix(CARD, ACCENT, 0.28), text_color="#FFFFFF" if has else TEXT2,
                             command=lambda: self.open_profile(list(exes), pname or title))
        if exes:
            prof.pack(side="right", before=txt)

        def style(*_):
            on = var.get()
            row.configure(fg_color=mix(CARD, ACCENT, 0.08) if on else CARD,
                          border_color=mix(CARD, ACCENT, 0.6) if on else CARD)

        def flip(_e=None):
            var.set(not var.get())
            style()

        cb.configure(command=style)
        for w in (row, txt, l1, l2, badge):
            w.bind("<Button-1>", flip)
        style()

    def apply_apps(self):
        apps = []
        for var, exes in self.app_vars.values():
            if var.get():
                apps += [e for e in exes if e.lower() not in {a.lower() for a in apps}]
        self.cfg["apps"] = apps
        self.update_app_set()
        self.update_applied_label(just_applied=True)
        self.refresh()

    def update_applied_label(self, just_applied=False):
        txt = (T("Đang áp dụng cho: ") + ", ".join(self.cfg["apps"])) if self.cfg["apps"] else T("Chưa chọn ứng dụng nào.")
        if just_applied:
            txt = T("✓ Đã áp dụng.  ") + txt
        self.applied_label.configure(text=txt, text_color=CYAN_TEXT if just_applied else TEXT2)

    def set_all_apps(self):
        self.cfg["all_apps"] = bool(self.all_var.get())
        self.refresh()

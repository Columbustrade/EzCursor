"""Hồ sơ riêng cho từng game."""

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from ..base import APP_NAME
from ..i18n import T
from ..config import STYLE_KEYS


class ProfilesMixin:
    def profile_label(self, pr):
        return T("Mặc định (mọi game)") if pr is None else pr["name"]

    def update_profile_menus(self):
        values = [self.profile_label(None)] + [pr["name"] for pr in self.cfg["profiles"]]
        cur = self.profile_label(self.edit_profile)
        for menu, rm in self.profile_menus:
            try:
                menu.configure(values=values)
                menu.set(cur)
                if self.edit_profile is None:
                    rm.pack_forget()
                elif not rm.winfo_ismapped():
                    rm.pack(side="left", padx=(6, 0))
            except tk.TclError:
                pass

    def profile_for_exe(self, exe):
        exe = (exe or "").lower()
        for pr in self.cfg["profiles"]:
            if exe in (e.lower() for e in pr["exes"]):
                return pr
        return None

    def style_of(self, pr):
        return self.cfg.base if pr is None else pr["style"]

    def pick_profile(self, label):
        pr = next((p for p in self.cfg["profiles"] if p["name"] == label), None)
        self.edit_profile = pr
        self.tray_pr = pr
        self.update_profile_menus()
        if not self.active:
            self.use_style(self.style_of(pr))

    def use_style(self, style, force=False):
        """Chuyển cài đặt kiểu con trỏ sang bộ khác và vẽ lại."""
        if style is self.cfg.target and not force:
            return
        self.cfg.target = style
        self.load_style_image()
        try:
            hidden = not self.win.winfo_viewable()
        except tk.TclError:
            hidden = False
        if hidden:          # cửa sổ đang ẩn (đang chơi game): chỉ đổi con trỏ, giao diện cập nhật khi mở lại
            self.rebuild_overlay()
            self.update_status()
            self.ui_dirty = True
            return
        self.sync_style_widgets()
        self.refresh()

    def sync_style_widgets(self):
        """Cập nhật các ô điều khiển giữ trạng thái riêng theo bộ kiểu đang chọn."""
        c = self.cfg
        try:
            self.size_slider.set(c["size"])
            self.tint_var.set(c["tint_image"])
            self.glow_var.set(c["glow"])
            self.hot_seg.set(T(c["hotspot"]))
            self.img_label.configure(text=Path(c["image"]).name if c["image"] and self.src_img is not None
                                     else T("(chưa có ảnh)"))
            if getattr(self, "style_seg", None):
                self.style_seg.set({v: k for k, v in self.style_map.items()}.get(c["bibata_style"]))
                self.hand_seg.set({v: k for k, v in self.hand_map.items()}.get(c["bibata_hand"]))
            self.fx_color_seg.set({v: k for k, v in self.fx_color_map.items()}.get(c["fx_color"]))
            self.fx_dens_seg.set({v: k for k, v in self.fx_dens_map.items()}.get(c["fx_density"]))
            for side in ("left", "right"):
                self.hold_vars[side].set(c[f"hold_{side}"])
                col = c[f"hold_{side}_color"]
                self.hold_btns[side].configure(fg_color=col, hover_color=col)
        except (tk.TclError, AttributeError):
            pass

    def create_profile(self, title, exes):
        """Tạo hồ sơ riêng (sao chép kiểu Mặc định) cho game, rồi mở tab Con trỏ để chỉnh."""
        names = {pr["name"] for pr in self.cfg["profiles"]}
        name, i = title, 2
        while name in names or name == self.profile_label(None):
            name, i = f"{title} {i}", i + 1
        st = {k: self.cfg.base[k] for k in STYLE_KEYS}
        st = json.loads(json.dumps(st))
        pr = {"name": name, "exes": list(exes), "style": st}
        self.cfg["profiles"].append(pr)
        self.tray_pr = pr
        added = [e for e in exes if e.lower() not in self.app_set]
        if added:                # game có hồ sơ riêng thì chắc chắn được áp dụng
            self.cfg["apps"] = self.cfg["apps"] + added
            self.update_app_set()
            self.update_applied_label()
        self.edit_profile = pr
        self.update_profile_menus()
        self.use_style(pr["style"])
        self.show_tab("cursor")
        self.save()

    def open_profile(self, exes, title):
        pr = next((self.profile_for_exe(e) for e in exes if self.profile_for_exe(e)), None)
        if pr is None:
            self.create_profile(title, exes)
            return
        self.edit_profile = pr
        self.tray_pr = pr
        self.update_profile_menus()
        self.use_style(pr["style"])
        self.show_tab("cursor")

    def delete_profile(self):
        pr = self.edit_profile
        if pr is None:
            return
        if not messagebox.askyesno(APP_NAME, T("Xóa hồ sơ riêng \"{n}\"? Game này sẽ dùng lại kiểu Mặc định.")
                                   .format(n=pr["name"]), parent=self.win):
            return
        img = pr["style"].get("image")
        if img and Path(img).name.startswith("custom-"):
            try:
                Path(img).unlink()
            except OSError:
                pass
        self.cfg["profiles"].remove(pr)
        self.edit_profile = None
        self.play_profile = None
        if self.tray_pr is pr:
            self.tray_pr = None
        self.update_profile_menus()
        self.use_style(self.cfg.base, force=True)
        if self.tab == "apps":
            self.refresh_apps()

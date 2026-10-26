"""Phần chỉnh phím tắt và kiểm tra phím tắt khi chạy."""

import json
import tkinter as tk

import customtkinter as ctk

from ..system import key_down
from ..i18n import T
from ..hotkeys import HOTKEY_MODS, HOTKEY_VKS, hotkey_parts, mods_down, vk_name
from ..config import DEFAULT_CFG
from ..theme import ACCENT, AMBER, BG, MUTED, PRESET_COLORS, TEXT, TEXT2


class HotkeysMixin:
    def update_hotkey_ui(self):
        hk = self.cfg["hotkeys"]
        for act, caps in getattr(self, "hotkey_caps", {}).items():
            for w in caps.winfo_children():
                w.destroy()
            for key in hotkey_parts(hk[act], act):
                k = ctk.CTkLabel(caps, text=key, font=self.F.m(11), text_color=TEXT, fg_color="#181C26",
                                 corner_radius=6, width=10, height=24)
                k.pack(side="left", padx=2)
                k.bind("<Button-1>", lambda e, a=act: self.capture_hotkey(a))
        if getattr(self, "toggle_hint", None):
            self.toggle_hint.configure(text=" + ".join(hotkey_parts(hk["toggle"], "toggle")))

    def reset_hotkeys(self):
        self.cfg["hotkeys"] = json.loads(json.dumps(DEFAULT_CFG["hotkeys"]))
        self.update_hotkey_ui()
        self.save()

    def hotkey_conflict(self, act, new):
        """Tên hành động đang dùng tổ hợp phím này (nếu trùng)."""
        names = {"toggle": "Bật / tắt", "shape": "Đổi hình dạng", "color": "Đổi màu", "quit": "Thoát",
                 "find": "Tìm con trỏ"}
        combos = {}
        for a, b in self.cfg["hotkeys"].items():
            b = new if a == act else b
            mods = frozenset(b["mods"])
            vks = range(0x31, 0x36) if a == "color" else [b["vk"]]
            for vk in vks:
                if (mods, vk) in combos and a != combos[(mods, vk)]:
                    other = combos[(mods, vk)]
                    return T(names[other if other != act else a])
                combos[(mods, vk)] = a
        return None

    def capture_hotkey(self, act):
        """Hộp thoại nhỏ chờ người dùng bấm tổ hợp phím mới."""
        if self.capturing:
            return
        self.capturing = True
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        d.title(T("Đổi phím tắt"))
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.transient(self.win)
        frm = ctk.CTkFrame(d, fg_color="transparent")
        frm.pack(fill="both", padx=22, pady=18)
        hint = (T("Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím số từ 1 đến 5.") if act == "color"
                else T("Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím chữ, số hoặc F1–F12."))
        ctk.CTkLabel(frm, text=T("Nhấn tổ hợp phím mới"), font=self.F.h(18), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(frm, text=hint, font=self.F.b(12), text_color=TEXT2, wraplength=360,
                     justify="left").pack(anchor="w", pady=(4, 12))
        live = ctk.CTkLabel(frm, text="…", font=self.F.m(16), text_color=ACCENT, height=36)
        live.pack(anchor="w")
        msg = ctk.CTkLabel(frm, text=T("Bấm Esc để hủy."), font=self.F.b(12), text_color=MUTED)
        msg.pack(anchor="w", pady=(8, 0))
        state = {"seen_clear": False}

        def close():
            self.capturing = False
            self.prev_keys = {"*"}          # tránh kích hoạt phím vừa bấm
            try:
                d.destroy()
            except tk.TclError:
                pass

        def poll():
            if not d.winfo_exists():
                self.capturing = False
                return
            mods = mods_down()
            keys = [vk for vk in HOTKEY_VKS if key_down(vk)]
            if not mods and not keys:
                state["seen_clear"] = True
            if key_down(0x1B):              # Esc
                close()
                return
            labels = [label for m, _, label in HOTKEY_MODS if m in mods]
            live.configure(text=" + ".join(labels + [vk_name(k) for k in keys[:1]]) or "…")
            if state["seen_clear"] and keys:
                vk = keys[0]
                if not ({"ctrl", "alt"} & mods):
                    msg.configure(text=T("Cần giữ Ctrl hoặc Alt."), text_color=AMBER)
                elif act == "color" and not 0x31 <= vk <= 0x35:
                    msg.configure(text=T("Đổi màu dùng các phím số 1–5."), text_color=AMBER)
                else:
                    new = {"mods": [m for m, _, _ in HOTKEY_MODS if m in mods]}
                    if act != "color":
                        new["vk"] = vk
                    other = self.hotkey_conflict(act, new)
                    if other:
                        msg.configure(text=T("Trùng với phím của: ") + other, text_color=AMBER)
                    else:
                        self.cfg["hotkeys"][act] = new
                        self.update_hotkey_ui()
                        self.save()
                        close()
                        return
                state["seen_clear"] = False
            d.after(30, poll)

        d.protocol("WM_DELETE_WINDOW", close)
        try:   # đặt hộp thoại giữa cửa sổ chính
            d.update_idletasks()
            x = self.win.winfo_rootx() + (self.win.winfo_width() - d.winfo_width()) // 2
            y = self.win.winfo_rooty() + (self.win.winfo_height() - d.winfo_height()) // 3
            d.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        d.after(100, d.lift)
        d.after(150, d.focus_force)
        d.after(200, poll)

    def check_hotkeys(self):
        if self.capturing:
            return True
        now = set()
        down = mods_down()
        if down & {"ctrl", "alt"}:
            hk = self.cfg["hotkeys"]
            for act in ("toggle", "shape", "quit", "find"):
                if set(hk[act]["mods"]) == down and key_down(hk[act]["vk"]):
                    now.add(act)
            if set(hk["color"]["mods"]) == down:
                for i in range(5):
                    if key_down(0x31 + i):
                        now.add(f"c{i}")
        elif self.prev_keys == {"*"}:
            self.prev_keys = set()
        if self.prev_keys == {"*"}:
            return True
        for act in now - self.prev_keys:
            if act.startswith("c"):
                self.set_color(PRESET_COLORS[int(act[1])])
            elif act == "shape":
                self.next_shape()
            elif act == "toggle":
                self.toggle()
            elif act == "find":
                self.start_find()
            elif act == "quit":
                self.quit()
                return False
        self.prev_keys = now
        return True

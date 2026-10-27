"""Kiểm tra và tải bản cập nhật từ GitHub."""

import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ..base import APP_NAME, APP_VERSION, res_path
from ..i18n import T
from ..colors import mix
from ..display import fetch_latest_release, parse_version, update_configured, verify_download
from ..theme import ACCENT, BG, BORDER, CARD, CYAN, MUTED, TEXT, TEXT2


class UpdateMixin:
    def set_auto_update(self):
        self.cfg["auto_check_update"] = bool(self.auto_upd_var.get())
        self.save()

    def auto_check_update(self):
        if (self.cfg["auto_check_update"] and update_configured()
                and time.time() - self.cfg["last_update_check"] > 20 * 3600):
            self.check_update(manual=False)
        self.ov.after(6 * 3600 * 1000, self.auto_check_update)

    def check_update(self, manual):
        if not update_configured():
            if manual:
                messagebox.showinfo(APP_NAME, T("Chưa cấu hình GITHUB_REPO trong mã nguồn."), parent=self.win)
            return
        if self.checking_update:
            return
        self.checking_update = True
        self.upd_label.configure(text=T("Đang kiểm tra cập nhật..."))

        def work():
            try:
                self.q.put(("update_result", fetch_latest_release(), manual))
            except Exception as e:
                self.q.put(("update_error", str(e), manual))
        threading.Thread(target=work, daemon=True).start()

    def handle_update_msg(self, kind, data=None, manual=False):
        if kind == "update_result":
            self.checking_update = False
            self.cfg["last_update_check"] = time.time()
            self.save()
            info = data
            if parse_version(info["version"]) <= parse_version(APP_VERSION):
                self.upd_label.configure(text=T("Bạn đang dùng phiên bản mới nhất."))
                if manual:
                    messagebox.showinfo(APP_NAME, T("Bạn đang dùng phiên bản mới nhất") + f" ({APP_VERSION}).",
                                        parent=self.win)
                return
            self.upd_label.configure(text=T("Có phiên bản mới: ") + info["version"], text_color=ACCENT)
            if not manual and info["version"] == self.cfg["skipped_version"]:
                return
            if self.win.state() == "withdrawn":
                self.pending_update = info
                try:
                    self.icon.notify(T("Đã có EzCursor {v}. Mở EzCursor để cập nhật.").format(v=info["version"]), APP_NAME)
                except Exception:
                    pass
            else:
                self.show_update_dialog(info, manual)
        elif kind == "update_error":
            self.checking_update = False
            self.upd_label.configure(text=T("Không kiểm tra được cập nhật."))
            if manual:
                messagebox.showerror(APP_NAME, T("Không kiểm tra được cập nhật.\nHãy kiểm tra kết nối mạng.") + f"\n\n{data}",
                                     parent=self.win)
        elif kind == "dl_progress":
            self.dl_bar.set(data / 100)
            self.dl_label.configure(text=T("Đang tải...") + f" {data:.0f}%")
        elif kind == "dl_done":
            self.dl_label.configure(text=T("Đang cài đặt, EzCursor sẽ tự mở lại sau giây lát..."))
            try:
                subprocess.Popen([data, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH"])
            except Exception as e:
                messagebox.showerror(APP_NAME, T("Không chạy được bộ cài:") + f"\n{e}", parent=self.upd_dialog)
                return
            self.ov.after(200, self.quit)
        elif kind == "dl_error":
            self.btn_update.configure(state="normal")
            self.dl_label.configure(text=T("Tải về thất bại."))
            messagebox.showerror(APP_NAME, T("Tải bản cập nhật thất bại:") + f"\n{data}", parent=self.upd_dialog)

    def show_update_dialog(self, info, manual):
        d = ctk.CTkToplevel(self.ov, fg_color=BG)
        d.title(f"{APP_NAME} - " + T("Cập nhật"))
        d.resizable(False, False)
        d.attributes("-topmost", True)
        ico = res_path("ezcursor.ico")
        if ico.exists():
            d.after(260, lambda: d.iconbitmap(str(ico)))
        self.upd_dialog = d
        frm = ctk.CTkFrame(d, fg_color="transparent")
        frm.pack(fill="both", padx=20, pady=18)
        self.caps(frm, "CÓ PHIÊN BẢN MỚI", CYAN).pack(anchor="w")
        title = ctk.CTkFrame(frm, fg_color="transparent")
        title.pack(anchor="w", pady=(2, 10))
        ctk.CTkLabel(title, text="EZCURSOR ", font=self.F.h(22), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(title, text=info["version"], font=self.F.h(22), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(title, text=T("   (bạn đang dùng {v})").format(v=APP_VERSION), font=self.F.b(12),
                     text_color=TEXT2).pack(side="left")
        self.caps(frm, "CÓ GÌ MỚI").pack(anchor="w")
        tb = ctk.CTkTextbox(frm, width=520, height=200, fg_color=CARD, border_color=BORDER, border_width=1,
                            corner_radius=10, font=self.F.b(13), text_color=TEXT, wrap="word")
        tb.insert("1.0", info["notes"].strip() or T("(không có ghi chú)"))
        tb.configure(state="disabled")
        tb.pack(fill="x", pady=(6, 12))
        self.dl_bar = ctk.CTkProgressBar(frm, progress_color=ACCENT, fg_color="#1A1E29", height=8)
        self.dl_bar.set(0)
        self.dl_bar.pack(fill="x")
        self.dl_label = ctk.CTkLabel(frm, text="", font=self.F.b(12), text_color=TEXT2)
        self.dl_label.pack(anchor="w")
        bf = ctk.CTkFrame(frm, fg_color="transparent")
        bf.pack(fill="x", pady=(8, 0))
        if info["url"]:
            self.btn_update = ctk.CTkButton(bf, text=T("CẬP NHẬT NGAY"), command=lambda: self.start_download(info),
                                            height=42, corner_radius=10, fg_color=ACCENT,
                                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        else:
            self.btn_update = ctk.CTkButton(bf, text=T("MỞ TRANG TẢI VỀ"), command=lambda: webbrowser.open(info["page"]),
                                            height=42, corner_radius=10, fg_color=ACCENT,
                                            hover_color=mix(ACCENT, "#FFFFFF", 0.15), font=self.F.h(14))
        self.btn_update.pack(side="right")
        ctk.CTkButton(bf, text=T("Để sau"), command=d.destroy, height=42, width=90, corner_radius=10,
                      fg_color="transparent", hover_color="#161A23", border_width=1, border_color=BORDER,
                      text_color=TEXT2, font=self.F.b(13, strong=True)).pack(side="right", padx=8)
        if not manual:
            def skip():
                self.cfg["skipped_version"] = info["version"]
                self.save()
                d.destroy()
            ctk.CTkButton(bf, text=T("Bỏ qua phiên bản này"), command=skip, height=42, corner_radius=10,
                          fg_color="transparent", hover_color="#161A23", text_color=MUTED,
                          font=self.F.b(12)).pack(side="left")
        d.after(100, d.lift)
        d.after(150, d.focus_force)

    def start_download(self, info):
        self.btn_update.configure(state="disabled")
        dest = Path(tempfile.mkdtemp(prefix="EzCursor-")) / f"EzCursor_Setup_{info['version']}.exe"

        def work():
            try:
                req = urllib.request.Request(info["url"], headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
                with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
                    total = int(r.headers.get("Content-Length") or info["size"] or 0)
                    done = 0
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.q.put(("dl_progress", min(100.0, done * 100 / total)))
                if not verify_download(dest, info.get("size", 0), info.get("sha256", "")):
                    dest.unlink(missing_ok=True)
                    raise ValueError(T("File tải về không đầy đủ hoặc bị lỗi, hãy thử lại."))
                self.q.put(("dl_done", str(dest)))
            except Exception as e:
                self.q.put(("dl_error", str(e)))
        threading.Thread(target=work, daemon=True).start()

"""Kho con trỏ trực tuyến (Bộ sưu tập > Trực tuyến)."""

import hashlib
import io
import json
import threading
import time
import urllib.parse
import urllib.request
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from ..base import APP_NAME, MY_DIR, log
from ..i18n import T
from ..config import CATALOG_URL, CAT_DIR, CAT_MAX, catalog_name, clean_catalog, http_get, unique_my_path
from ..curfile import load_cursor_file
from ..theme import AMBER, GREEN, TEXT2


class CatalogMixin:
    def cat_file(self, cid):
        name = self.cfg["catalog_got"].get(cid)
        if not name:
            return None
        f = MY_DIR / name
        return f if f.is_file() else None

    def cat_thumb_path(self, e):
        return CAT_DIR / f"{e['id']}-{e['sha256'][:8]}.png"

    def start_catalog(self, force=False):
        if self.cat_busy:
            return
        self.cat_busy = True
        self.cat_status = ("loading", 0)
        self.update_cat_label()

        def work():
            try:
                data = json.loads(http_get(CATALOG_URL, 512 * 1024).decode("utf-8"))
                entries = clean_catalog(data)
                try:
                    CAT_DIR.mkdir(parents=True, exist_ok=True)
                    (CAT_DIR / "catalog.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
                self.q.put(("cat_list", entries, True))
                self.fetch_thumbs(entries)
            except Exception as ex:
                log.warning("Kho trực tuyến: %s", ex)
                self.q.put(("cat_error", str(ex)))
            finally:
                self.q.put(("cat_end",))

        threading.Thread(target=work, daemon=True).start()

    def fetch_thumbs(self, entries):
        for e in entries:
            path = self.cat_thumb_path(e)
            if path.exists():
                continue
            try:
                data = http_get(urllib.parse.urljoin(CATALOG_URL, e["thumb"]), 512 * 1024)
                Image.open(io.BytesIO(data)).verify()
                path.write_bytes(data)
                self.q.put(("cat_thumb", e["id"]))
            except Exception as ex:
                log.warning("Ảnh nhỏ %s: %s", e["id"], ex)

    def handle_catalog(self, cmd, *args):
        if cmd == "cat_list":
            entries, online = args
            self.cat_entries = entries
            self.cat_status = ("ok" if online else "offline", len(entries))
            self.build_online_tiles()
        elif cmd == "cat_error":
            if self.cat_entries is None:
                try:
                    data = json.loads((CAT_DIR / "catalog.json").read_text(encoding="utf-8"))
                    self.handle_catalog("cat_list", clean_catalog(data), False)
                    return
                except Exception:
                    pass
            if self.cat_status[0] != "offline":
                self.cat_status = ("error", 0)
        elif cmd == "cat_end":
            self.cat_busy = False
        elif cmd == "cat_thumb":
            self.set_cat_tile(args[0])
        elif cmd == "cat_done":
            cid, path = args
            self.cat_dl.discard(cid)
            self.cfg["catalog_got"] = dict(self.cfg["catalog_got"], **{cid: Path(path).name})
            self.rebuild_mine_tiles()
            self.use_my_cursor(path)
            self.set_cat_tile(cid)
            self.save()
        elif cmd == "cat_fail":
            cid, msg = args
            self.cat_dl.discard(cid)
            self.set_cat_tile(cid)
            messagebox.showerror(APP_NAME, T("Không tải được con trỏ:") + f"\n{T(msg)}", parent=self.win)
        self.update_cat_label()

    def update_cat_label(self):
        kind, n = self.cat_status
        txt = {"loading": T("Đang tải danh sách…"),
               "ok": T("{n} con trỏ · Bấm để tải về, con trỏ sẽ nằm trong mục Của bạn.").format(n=n),
               "offline": T("Đang xem danh sách lưu lần trước (chưa kết nối được)."),
               "error": T("Không kết nối được kho trực tuyến. Kiểm tra mạng rồi bấm Làm mới.")}.get(kind, "")
        try:
            self.cat_label.configure(text=txt, text_color=AMBER if kind in ("error", "offline") else TEXT2)
        except (tk.TclError, AttributeError):
            pass

    def build_online_tiles(self):
        grid = getattr(self, "lib_grids", {}).get("online")
        if grid is None:
            return
        for w in grid.winfo_children():
            w.destroy()
        self.cat_tiles = {}
        cols = 5
        today = time.strftime("%Y-%m-%d")
        for i, e in enumerate(self.cat_entries or []):
            b = ctk.CTkButton(grid, text="", compound="top", height=104, width=10, corner_radius=12,
                              border_width=1, font=self.F.b(12), command=lambda e=e: self.online_pick(e))
            b.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            self.cat_tiles[e["id"]] = b
            try:
                age = (time.mktime(time.strptime(today, "%Y-%m-%d"))
                       - time.mktime(time.strptime(e["added"], "%Y-%m-%d"))) / 86400
            except ValueError:
                age = 999
            if age <= 30:
                ctk.CTkLabel(b, text=T("MỚI"), font=self.F.m(9), text_color="#0B0D12", fg_color=GREEN,
                             corner_radius=6, height=16, width=10).place(x=8, y=7)
            self.set_cat_tile(e["id"])
        self.update_cat_label()
        self.update_library()

    def set_cat_tile(self, cid):
        b = getattr(self, "cat_tiles", {}).get(cid)
        e = next((x for x in self.cat_entries or [] if x["id"] == cid), None)
        if b is None or e is None:
            return
        name = catalog_name(e)
        name = name if len(name) <= 18 else name[:16] + "…"
        state = (T("Đang tải…") if cid in self.cat_dl else T("✓ Đã có") if self.cat_file(cid) else T("Tải về"))
        img = self.cat_thumbs.get(cid)
        if img is None:
            try:
                pic = Image.open(self.cat_thumb_path(e)).convert("RGBA")
                img = self.cat_thumbs[cid] = ctk.CTkImage(pic, size=(56, 56))
            except Exception:
                img = ctk.CTkImage(Image.new("RGBA", (112, 112), (0, 0, 0, 0)), size=(56, 56))
        try:
            b.configure(text=f"{name}\n{state}", image=img)
        except tk.TclError:
            pass

    def online_pick(self, e):
        cid = e["id"]
        f = self.cat_file(cid)
        if f is not None:
            self.use_my_cursor(f)
            return
        if cid in self.cat_dl:
            return
        self.cat_dl.add(cid)
        self.set_cat_tile(cid)
        name = catalog_name(e)

        def work():
            try:
                data = http_get(urllib.parse.urljoin(CATALOG_URL, e["file"]), min(e["size"] + 1024, CAT_MAX))
                if hashlib.sha256(data).hexdigest() != e["sha256"]:
                    raise ValueError("File không khớp mã kiểm tra")
                MY_DIR.mkdir(parents=True, exist_ok=True)
                dest = unique_my_path(name + Path(e["file"]).suffix.lower())
                dest.write_bytes(data)
                try:
                    load_cursor_file(str(dest))
                except Exception:
                    dest.unlink()
                    raise ValueError("File con trỏ bị lỗi")
                self.q.put(("cat_done", cid, str(dest)))
            except Exception as ex:
                log.warning("Tải %s: %s", cid, ex)
                self.q.put(("cat_fail", cid, str(ex)))

        threading.Thread(target=work, daemon=True).start()

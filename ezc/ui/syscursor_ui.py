"""Chế độ "Con trỏ thật" phía ứng dụng (đang ẩn, xem syscursor.py)."""

from pathlib import Path

from ..base import APP_NAME, log
from ..winapi import user32
from ..syscursor import (
    REAL_CURSOR_MODE, SYS_CURSOR_IDS, current_cursor, is_system_cursor, make_hcursor,
    restore_system_cursors, set_system_cursors)
from ..i18n import T


class SysCursorMixin:
    def system_mode(self):
        """Đang dùng Con trỏ thật cho cửa sổ hiện tại (game tự đặt con trỏ riêng thì dùng Lớp phủ)."""
        return (REAL_CURSOR_MODE and self.cfg["cursor_mode"] == "system"
                and (getattr(self, "fg_exe", "") or "").lower() not in self.cfg["sys_skip"])

    def check_game_cursor(self, now):
        """Chế độ Con trỏ thật: game nào tự đặt / tự vẽ con trỏ thì ghi nhớ và chuyển game đó sang Lớp phủ."""
        if now - getattr(self, "gc_t", 0) < 0.5:
            return
        self.gc_t = now
        try:
            showing, h = current_cursor()
        except Exception:
            return
        foreign = (not showing) or (h is not None and not is_system_cursor(h))
        self.gc_hits = (getattr(self, "gc_hits", 0) + 1) if foreign else 0
        if self.gc_hits < 4:          # ~2 giây liên tục mới kết luận
            return
        self.gc_hits = 0
        exe = (self.fg_exe or "").lower()
        if not exe or exe in self.cfg["sys_skip"]:
            return
        self.cfg["sys_skip"] = self.cfg["sys_skip"] + [exe]
        log.info("Con trỏ thật: %s %s -> dùng Lớp phủ cho game này", exe,
                 "ẩn con trỏ Windows" if not showing else f"tự đặt con trỏ riêng ({h})")
        self.save()
        self.set_active(False)
        self.set_active(True)
        try:
            self.icon.notify(T("{g} dùng con trỏ riêng của game nên chế độ Con trỏ thật không đổi được. "
                               "EzCursor đã chuyển sang Lớp phủ cho game này.").format(g=Path(exe).stem), APP_NAME)
        except Exception:
            pass

    def apply_system_cursor(self, force=False):
        """Chế độ Con trỏ thật: đặt con trỏ Windows thành con trỏ EzCursor (theo trạng thái giữ chuột)."""
        key = self.hold_state if self.hold_state in self.variants else None
        if key == self.sys_key and not force:
            return
        comp = self.variants.get(key) or self.composed
        if comp is None:
            return
        try:
            hc = self.sys_cache.get(key)
            if hc is None:
                hc = make_hcursor(comp[0], comp[1])
                self.sys_cache[key] = hc
            ok, errs = set_system_cursors(hc)
            self.sys_key = key
            if not getattr(self, "sys_logged", False) or errs:
                self.sys_logged = True
                log.info("Con trỏ thật: đặt %d/%d con trỏ Windows, ảnh %s, cửa sổ đang mở: %s%s", ok,
                         len(SYS_CURSOR_IDS), comp[0].size, self.fg_exe or "?", (" | lỗi " + ", ".join(errs[:4])) if errs else "")
        except Exception:
            self.report_error("system cursor", once=True)

    def clear_system_cursor(self):
        restore_system_cursors()
        self.sys_key = "?"

    def drop_system_cache(self):
        for hc in self.sys_cache.values():
            try:
                user32.DestroyCursor(hc)
            except Exception:
                pass
        self.sys_cache = {}
        self.sys_key = "?"

    def set_cursor_mode(self, mode):
        if mode == self.cfg["cursor_mode"]:
            return
        self.set_active(False)          # tắt theo chế độ cũ; vòng lặp sẽ bật lại theo chế độ mới
        self.clear_system_cursor()
        self.cfg["cursor_mode"] = mode
        if mode == "system":
            self.cfg["sys_skip"] = []
        self.update_mode_ui()
        self.save()
        if mode == "system":          # cho xem thử ngay 3 giây trên màn hình hiện tại
            self.apply_system_cursor(force=True)
            self.ov.after(3000, lambda: None if (self.active and self.system_mode()) else self.clear_system_cursor())

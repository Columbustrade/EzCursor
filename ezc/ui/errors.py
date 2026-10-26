"""Xử lý lỗi: ghi nhật ký, chế độ an toàn."""

import sys
import time
import traceback

from ..base import APP_NAME, log
from ..system import emergency_cursor
from ..i18n import T


class ErrorsMixin:
    def report_error(self, where, once=False, exc_info=None):
        """Ghi lỗi vào log; lỗi lặp lại liên tục ở vòng lặp chính thì tạm tắt con trỏ cho an toàn."""
        exc_info = exc_info or sys.exc_info()
        exc = exc_info[1]
        key = (where, type(exc).__name__, str(exc)[:200])
        if once and key in self.logged_errors:
            return
        if len(self.logged_errors) < 200:
            self.logged_errors.add(key)
            log.error("Lỗi ở %s:\n%s", where, "".join(traceback.format_exception(*exc_info)))
        if once:
            return
        now = time.perf_counter()
        self.err_times = [t for t in self.err_times if now - t < 10] + [now]
        if len(self.err_times) >= 15 and not self.safe_mode:
            self.enter_safe_mode()

    def on_tk_error(self, exc_type, exc, tb):
        if self.quitting:
            return
        self.report_error("giao diện", exc_info=(exc_type, exc, tb))

    def enter_safe_mode(self):
        self.safe_mode = True
        log.critical("Lỗi lặp lại liên tục, tạm tắt con trỏ EzCursor.")
        emergency_cursor()
        self.sys_key = "?"
        try:
            self.active = False
            self.ovl.show(False)
            self.fxw.show(False)
        except Exception:
            pass
        try:
            self.icon.notify(T("EzCursor gặp lỗi liên tục nên đã tạm tắt con trỏ để bạn dùng chuột bình thường. "
                               "Hãy mở lại EzCursor; chi tiết lỗi nằm trong file ezcursor.log."), APP_NAME)
        except Exception:
            pass

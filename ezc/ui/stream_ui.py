"""Chế độ stream: bật / tắt máy chủ cho nguồn Browser của OBS và dòng cài đặt trong tab Tùy chọn."""

from tkinter import messagebox

from ..base import APP_NAME, log
from ..i18n import T
from ..stream import StreamServer, game_view


class StreamMixin:
    def start_stream(self):
        """Mở máy chủ (nếu chưa mở); lỗi thì báo và trả False."""
        if self.stream is not None:
            return True
        s = StreamServer(self.cfg["stream_port"], game_view, lambda: self.follow.find_hot or self.follow.hot)
        try:
            port = s.start()
        except OSError as e:
            log.warning("Không mở được chế độ stream: %s", e)
            messagebox.showerror(APP_NAME, T("Không mở được chế độ stream:") + f"\n{e}", parent=self.win)
            return False
        self.stream = s
        self.cfg["stream_port"] = port           # giữ link cố định cho các lần sau
        self.ovl.target = s
        log.info("Chế độ stream: %s", s.url)
        return True

    def stop_stream(self):
        s, self.stream = self.stream, None
        self.ovl.target = None
        if s is not None:
            s.stop()

    def set_stream(self):
        on = bool(self.stream_var.get())
        if on and not self.start_stream():
            on = False
            self.stream_var.set(False)
        if not on:
            self.stop_stream()
        self.cfg["stream"] = on
        self.save()
        self.update_stream_ui()

    def copy_stream_link(self):
        if self.stream is not None:
            self.win.clipboard_clear()
            self.win.clipboard_append(self.stream.url)

    def update_stream_ui(self):
        if self.stream is not None:
            self.stream_sub.configure(text=T("Dán link vào nguồn Browser của OBS: ") + self.stream.url)
            self.stream_copy.pack(side="right", padx=(0, 10))
        else:
            self.stream_sub.configure(text=T("Cho người xem stream thấy con trỏ EzCursor qua nguồn Browser của OBS."))
            self.stream_copy.pack_forget()

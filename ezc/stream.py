"""Chế độ stream: máy chủ web cục bộ để OBS (nguồn Browser) hiện đúng con trỏ EzCursor trên stream.

Không đụng vào game: trang /cursor nhận ảnh con trỏ + vị trí chuột qua Server-Sent Events rồi tự vẽ."""

import ctypes
import io
import json
import threading
from collections import OrderedDict
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .base import log
from .winapi import user32


user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>EzCursor</title>
<style>html,body{margin:0;background:transparent;overflow:hidden}canvas{display:block}</style></head>
<body><canvas id="c"></canvas><script>
const c = document.getElementById("c"), g = c.getContext("2d");
let img = null, pos = null, want = null, dirty = true;
function fit() { c.width = innerWidth; c.height = innerHeight; dirty = true; }
addEventListener("resize", fit); fit();
const es = new EventSource("/events");
es.addEventListener("img", e => {
  const d = JSON.parse(e.data), im = new Image();
  want = d.id;
  im.onload = () => { if (want === d.id) { img = {im: im, w: d.w, h: d.h}; dirty = true; } };
  im.src = "/img/" + d.id + ".png";
});
es.addEventListener("pos", e => { pos = JSON.parse(e.data); dirty = true; });
es.onerror = () => { pos = null; dirty = true; };
(function draw() {
  if (dirty) {
    dirty = false;
    g.clearRect(0, 0, c.width, c.height);
    if (img && pos && pos.v && pos.gw > 0) {
      const k = c.width / pos.gw;     // khung OBS nhỏ hơn màn hình game thì con trỏ nhỏ lại tương ứng
      g.drawImage(img.im, pos.x * c.width - pos.hx * k, pos.y * c.height - pos.hy * k, img.w * k, img.h * k);
    }
  }
  requestAnimationFrame(draw);
})();
</script></body></html>
"""

KEEP = 64           # số ảnh gần nhất còn tải được (khung ombre / lấp lánh lặp lại)
TICK = 0.016        # ~60 lần/giây


def game_view():
    """(chuột x, chuột y, (trái, trên, rộng, cao) vùng nội dung của cửa sổ đang ở trên cùng) hoặc None.
    Game Capture của OBS ghi đúng vùng nội dung này (Borderless: cả màn hình; Windowed: phần trong khung)."""
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    h = user32.GetForegroundWindow()
    if not h:
        return None
    rc = wintypes.RECT()
    if not user32.GetClientRect(h, ctypes.byref(rc)) or rc.right <= 0 or rc.bottom <= 0:
        return None
    org = wintypes.POINT(0, 0)
    user32.ClientToScreen(h, ctypes.byref(org))
    return pt.x, pt.y, (org.x, org.y, rc.right, rc.bottom)


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False      # trên Windows SO_REUSEADDR cho mở trùng cổng đang dùng -> không phát hiện cổng bận


class StreamServer:
    """Máy chủ chỉ nghe 127.0.0.1. Luồng giao diện chỉ gọi publish_* (gán biến, không chờ);
    mã hóa PNG và gửi dữ liệu chạy trên luồng của máy chủ, chỉ khi có trang đang kết nối."""

    def __init__(self, port, locate, hot):
        self.port = port
        self.locate = locate        # () -> (x, y, (trái, trên, rộng, cao)) | None
        self.hot = hot              # () -> điểm click trong ảnh đang hiện
        self._lock = threading.Lock()
        self._n = 0
        self._cur = None            # (số thứ tự, ảnh) đang hiện
        self._imgs = OrderedDict()  # số -> ảnh (giữ KEEP ảnh gần nhất)
        self._png = OrderedDict()   # số -> PNG đã mã hóa
        self._visible = False
        self._stop = threading.Event()
        self._httpd = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/cursor"

    def start(self):
        """Mở máy chủ ở cổng port, bận thì thử 9 cổng kế tiếp. Trả về cổng thực dùng (hết cổng: OSError)."""
        err = None
        for p in range(self.port, self.port + 10):
            try:
                self._httpd = _HTTPServer(("127.0.0.1", p), self._handler_class())
                break
            except OSError as e:
                err = e
        else:
            raise err
        self.port = p
        self._stop.clear()
        threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.1},
                         name="EzCursorStream", daemon=True).start()
        return p

    def stop(self):
        self._stop.set()            # các kết nối /events thoát vòng lặp trong ~16 ms
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def publish_image(self, im):
        with self._lock:
            self._n += 1
            self._imgs[self._n] = im
            while len(self._imgs) > KEEP:
                self._imgs.popitem(last=False)
            self._cur = (self._n, im)

    def publish_visible(self, on):
        self._visible = bool(on)

    # ---- phía máy chủ (luồng riêng) ----

    def _handler_class(self):
        srv = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                srv._route(self)

        return Handler

    def _route(self, h):
        path = h.path.split("?", 1)[0]
        if path in ("/", "/cursor"):
            self._send(h, 200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif path == "/events":
            self._events(h)
        elif path.startswith("/img/") and path.endswith(".png") and path[5:-4].isdigit():
            png = self._png_for(int(path[5:-4]))
            if png is None:
                self._send(h, 404, "text/plain", b"not found")
            else:
                self._send(h, 200, "image/png", png)
        else:
            self._send(h, 404, "text/plain", b"not found")

    @staticmethod
    def _send(h, code, ctype, body):
        h.send_response(code)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(body)))
        h.send_header("Cache-Control", "no-store")
        h.end_headers()
        h.wfile.write(body)

    def _png_for(self, n):
        with self._lock:
            if n in self._png:
                return self._png[n]
            im = self._imgs.get(n)
        if im is None:
            return None
        buf = io.BytesIO()
        im.save(buf, format="PNG", compress_level=1)
        data = buf.getvalue()
        with self._lock:
            self._png[n] = data
            while len(self._png) > KEEP:
                self._png.popitem(last=False)
        return data

    def _position(self):
        try:
            loc = self.locate()
            hx, hy = self.hot()
        except Exception:
            loc, hx, hy = None, 0, 0
        pos = {"x": 0.0, "y": 0.0, "hx": int(hx), "hy": int(hy), "gw": 0, "v": False}
        if loc:
            x, y, (left, top, w, hgt) = loc
            if w > 0 and hgt > 0:
                pos.update(x=round((x - left) / w, 5), y=round((y - top) / hgt, 5), gw=int(w))
                inside = left <= x < left + w and top <= y < top + hgt
                pos["v"] = self._visible and inside and self._cur is not None
        return pos

    def _events(self, h):
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.send_header("Cache-Control", "no-store")
        h.end_headers()
        sent_img = sent_pos = None
        idle = 0
        try:
            while not self._stop.is_set():
                parts = []
                cur = self._cur
                if cur is not None and cur[0] != sent_img:
                    sent_img = cur[0]
                    w, hgt = cur[1].size
                    parts.append(("img", {"id": str(cur[0]), "w": w, "h": hgt}))
                pos = self._position()
                if pos != sent_pos:
                    sent_pos = pos
                    parts.append(("pos", pos))
                if parts:
                    idle = 0
                    h.wfile.write("".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in parts).encode("utf-8"))
                    h.wfile.flush()
                else:
                    idle += 1
                    if idle * TICK >= 5:              # giữ kết nối, đồng thời phát hiện trang đã đóng
                        idle = 0
                        h.wfile.write(b": ping\n\n")
                        h.wfile.flush()
                self._stop.wait(TICK)
        except OSError:
            pass                                    # trang / OBS đã đóng kết nối
        except Exception:
            log.exception("Lỗi gửi dữ liệu chế độ stream")

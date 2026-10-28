"""Kiểm thử chế độ stream: máy chủ cục bộ cho nguồn Browser của OBS."""
import base64
import http.client
import io
import json
import socket
import time
import urllib.request

from PIL import Image

from harness import ez

GAME = (0, 0, 1920, 1080)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_bytes(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.read()


def get(url):
    return get_bytes(url).decode("utf-8")


def open_events(port):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    c.request("GET", "/events")
    r = c.getresponse()
    assert r.status == 200 and r.getheader("Content-Type", "").startswith("text/event-stream")
    return c, r


def read_events(r, n):
    """Đọc n sự kiện SSE: [(tên, dữ liệu JSON)]."""
    out, name = [], None
    while len(out) < n:
        line = r.fp.readline().decode("utf-8").rstrip("\r\n")
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            out.append((name, json.loads(line[5:].strip())))
    return out


def until(r, pred, limit=40):
    """Đọc tới khi gặp sự kiện thỏa pred."""
    for _ in range(limit):
        ev = read_events(r, 1)[0]
        if pred(*ev):
            return ev[1]
    raise AssertionError("không thấy sự kiện mong đợi")


def server(locate=lambda: (960, 540, GAME), hot=lambda: (5, 6)):
    s = ez.StreamServer(free_port(), locate=locate, hot=hot)
    s.start()
    return s


class FakeOv:
    hwnd = 7
    visible = False

    def __init__(self):
        self.images = []

    def set_image(self, im, pos=None):
        self.images.append(im)

    def show(self, on):
        self.visible = on


class Rec:
    def __init__(self):
        self.images, self.visible = [], []

    def publish_image(self, im):
        self.images.append(im)

    def publish_visible(self, on):
        self.visible.append(on)


def test_mirror_forwards_and_publishes():
    inner = FakeOv()
    m = ez.OverlayMirror(inner)
    im = Image.new("RGBA", (8, 8))
    m.set_image(im)
    m.show(True)                        # chưa có target: chỉ chuyển tiếp
    assert inner.images == [im] and inner.visible and m.visible and m.hwnd == 7
    target = Rec()
    m.target = target
    assert target.images == [im] and target.visible == [True]     # đẩy ngay trạng thái hiện tại
    m.show(False)
    im2 = Image.new("RGBA", (4, 4))
    m.set_image(im2)
    assert target.visible == [True, False] and target.images == [im, im2]
    m.target = None
    m.set_image(im)                     # bỏ target: không còn gửi
    assert target.images == [im, im2]


def test_page_image_and_position():
    s = server()
    try:
        assert s.url == f"http://127.0.0.1:{s.port}/cursor"
        assert "EventSource" in get(s.url)
        s.publish_image(Image.new("RGBA", (32, 24), (255, 0, 0, 255)))
        s.publish_visible(True)
        c, r = open_events(s.port)
        img = until(r, lambda e, d: e == "img")
        pos = until(r, lambda e, d: e == "pos" and d["v"])
        c.close()
        assert (img["w"], img["h"], img["hx"], img["hy"]) == (32, 24, 5, 6)
        assert pos == {"x": 0.5, "y": 0.5, "gw": 1920, "v": True}
        assert png_of(img).size == (32, 24)
    finally:
        s.stop()


def png_of(img):
    return Image.open(io.BytesIO(base64.b64decode(img["png"])))


def test_hotspot_travels_with_its_image():
    """Điểm click gửi cùng ảnh (lấy lúc publish), không lấy lúc gửi: đổi ảnh không làm con trỏ trên stream giật."""
    hot = [(1, 2)]
    s = server(hot=lambda: hot[0])
    try:
        s.publish_image(Image.new("RGBA", (8, 8)))
        hot[0] = (90, 90)                      # ảnh khác (vd tìm con trỏ) sắp tới với điểm click khác
        c, r = open_events(s.port)
        img = until(r, lambda e, d: e == "img")
        c.close()
        assert (img["hx"], img["hy"]) == (1, 2)
    finally:
        s.stop()


def test_repeated_frames_keep_their_id():
    """Khung ombre / lấp lánh lặp lại (cùng đối tượng ảnh) giữ id cũ: không mã hóa lại PNG liên tục."""
    s = server()
    try:
        a, b = Image.new("RGBA", (8, 8)), Image.new("RGBA", (9, 9))
        c, r = open_events(s.port)
        ids = []
        for im in (a, b, a):
            s.publish_image(im)
            ids.append(until(r, lambda e, d: e == "img")["id"])
        c.close()
        assert ids[0] == ids[2] != ids[1]
    finally:
        s.stop()


def test_rejects_foreign_host():
    """Trang web lạ dùng DNS rebinding (Host khác 127.0.0.1 / localhost) không đọc được vị trí chuột."""
    s = server()
    try:
        for host, code in ((f"evil.example:{s.port}", 403), (f"localhost:{s.port}", 200), (f"127.0.0.1:{s.port}", 200)):
            c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=3)
            c.request("GET", "/cursor", headers={"Host": host})
            assert c.getresponse().status == code, host
            c.close()
    finally:
        s.stop()


def test_hidden_outside_game_or_no_window():
    for loc in ((2500, 540, GAME), None):
        s = server(locate=lambda loc=loc: loc)
        try:
            s.publish_image(Image.new("RGBA", (8, 8)))
            s.publish_visible(True)
            c, r = open_events(s.port)
            pos = until(r, lambda e, d: e == "pos")
            c.close()
            assert pos["v"] is False
        finally:
            s.stop()


def test_busy_port_uses_next():
    p = free_port()
    with socket.socket() as hold:
        hold.bind(("127.0.0.1", p))
        hold.listen()
        s = ez.StreamServer(p, locate=lambda: None, hot=lambda: (0, 0))
        try:
            assert s.start() != p and s.port != p
            assert "EventSource" in get(s.url)
        finally:
            s.stop()


def test_stop_with_open_client_is_fast():
    s = server()
    s.publish_image(Image.new("RGBA", (8, 8)))
    c, r = open_events(s.port)
    read_events(r, 1)
    t0 = time.perf_counter()
    s.stop()
    assert time.perf_counter() - t0 < 2
    c.close()
    try:
        get(s.url)
        raise AssertionError("máy chủ vẫn trả lời sau stop()")
    except OSError:
        pass


def test_two_clients_both_get_current_image():
    s = server()
    try:
        s.publish_image(Image.new("RGBA", (10, 12)))
        (c1, r1), (c2, r2) = open_events(s.port), open_events(s.port)
        a = until(r1, lambda e, d: e == "img")
        b = until(r2, lambda e, d: e == "img")
        c1.close()
        c2.close()
        assert a["id"] == b["id"] and (a["w"], a["h"]) == (10, 12)
    finally:
        s.stop()


def test_rapid_images_send_latest():
    s = server()
    try:
        c, r = open_events(s.port)
        until(r, lambda e, d: e == "pos")
        for i in range(1, 51):
            s.publish_image(Image.new("RGBA", (i, i)))
        last = None
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 2 and (last is None or last["w"] != 50):
            last = until(r, lambda e, d: e == "img")
        c.close()
        assert (last["w"], last["h"]) == (50, 50)
        assert png_of(last).size == (50, 50)
    finally:
        s.stop()

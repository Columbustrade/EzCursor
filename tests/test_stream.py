"""Kiểm thử chế độ stream: máy chủ cục bộ cho nguồn Browser của OBS."""
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
        assert (img["w"], img["h"]) == (32, 24)
        assert pos == {"x": 0.5, "y": 0.5, "hx": 5, "hy": 6, "gw": 1920, "v": True}
        png = Image.open(io.BytesIO(get_bytes(f"http://127.0.0.1:{s.port}/img/{img['id']}.png")))
        assert png.size == (32, 24)
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
        png = Image.open(io.BytesIO(get_bytes(f"http://127.0.0.1:{s.port}/img/{last['id']}.png")))
        assert png.size == (50, 50)
    finally:
        s.stop()

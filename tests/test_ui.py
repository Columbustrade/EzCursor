"""Kiểm thử giao diện và vòng lặp bám chuột với Windows giả lập (chạy dưới xvfb trên Linux)."""
import http.client
import json
import os
import threading
import re
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

import stubs
from harness import ez

AD = os.path.join(os.environ["APPDATA"], "EzCursor")


def check_test_dir():
    """Dừng ngay nếu AD không nằm trong thư mục tạm của kiểm thử (tránh xoá %APPDATA%\\EzCursor thật)."""
    ad = Path(AD).resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    own = Path(stubs.APPDATA).resolve()
    assert ad.is_relative_to(own) and own.is_relative_to(tmp) and own != tmp, \
        f"Từ chối xoá {ad}: không nằm trong thư mục tạm kiểm thử {own}"
    assert Path(ez.APP_DIR).resolve() == ad, f"App dùng {ez.APP_DIR}, kiểm thử dùng {ad}"


class FakeOverlay:
    visible = False
    hwnd = 0

    def __init__(self, *a, **k):
        self.moves = []

    def set_image(self, *a, **k):
        pass

    def move(self, x, y):
        self.moves.append(time.perf_counter())

    def show(self, on):
        self.visible = on

    def destroy(self):
        pass

    def raise_top(self):
        pass


def log_errors():
    log = open(os.path.join(AD, "ezcursor.log"), encoding="utf-8").read()
    blocks = re.split(r"\n(?=\d{4}-)", log)
    # iconbitmap: file .ico chỉ đọc được trên Windows
    return [b for b in blocks if " ERROR " in b and "iconbitmap" not in b]


@pytest.fixture
def app():
    check_test_dir()
    shutil.rmtree(AD, ignore_errors=True)
    os.makedirs(AD)
    json.dump({"splash": False, "setup_done": True, "all_apps": True, "shape": "EzDrop", "ombre": True, "ombre_anim": True,
               "profiles": [{"name": "LE", "exes": ["Last Epoch.exe"],
                             "style": {"shape": "ez_sword", "hold_left": True, "cursor_sparkle": True, "size": 96}}]},
              open(os.path.join(AD, "config.json"), "w"))
    ez.setup_logging()
    state = {"exe": "explorer.exe", "x": 100, "y": 300}

    def get_cursor_pos(p):
        try:
            p._obj.x, p._obj.y = state["x"], state["y"]
        except Exception:
            pass
        return 1

    ez.user32.GetCursorPos = get_cursor_pos
    ez.key_down = lambda vk: False
    ez.mouse_buttons = lambda: (False, False)
    ez.list_running_apps = lambda: [("Last Epoch.exe", "Last Epoch"), ("notepad.exe", "Notepad")]
    ez.shell_ui_open = lambda *a: False
    ez.fullscreen_exclusive = lambda: False
    ez.monitor_scale = lambda x, y: 1.0
    ez.foreground_exe = lambda: state["exe"]
    ez.is_startup_enabled = lambda: True
    ez.LayeredOverlay = FakeOverlay
    a = ez.App(start_in_tray=False)
    a.state = state
    yield a
    a.quit()
    for h in list(ez.log.handlers):     # Windows khoá file đang mở: đóng ezcursor.log để test sau xoá được AD
        ez.log.removeHandler(h)
        h.close()


def pump(app, n=15):
    for _ in range(n):
        app.ov.update()
        time.sleep(0.02)


def test_every_screen_opens(app):
    pump(app)
    for lang in ("vi", "en", "vi"):
        app.set_language(lang)
        pump(app)
        for tab in list(app.pages):
            app.show_tab(tab)
            pump(app, 5)
        for view in ("ez", "bibata", "mine", "online"):
            app.set_lib_view(view)
            pump(app, 5)
    app.open_maker()
    pump(app)
    app.run_setup()
    pump(app)
    app.hide_to_tray()
    app.show_window()
    pump(app)
    assert not log_errors()


def test_style_changes(app):
    app.next_shape()
    app.set_color("#22D3EE")
    app.set_ombre(True)
    app.set_ombre_speed("fast")
    app.set_size(96)
    app.toggle_fav(app.current_fav_id())
    app.create_profile("Notepad", ["notepad.exe"])
    app.build_tray_menu()
    pump(app)
    assert app.cfg["color"] == "#22D3EE" and app.cfg["size"] == 96 and len(app.cfg["favorites"]) == 1
    assert any(p["name"] == "Notepad" for p in app.cfg["profiles"])
    assert not log_errors()


def test_follow_has_no_stalls(app):
    """Con trỏ phải bám chuột đều tay, kể cả lúc vào game (đổi hồ sơ, dựng khung hình mới)."""
    app.hide_to_tray()

    def run(sec):
        app.ovl.moves.clear()
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < sec:
            app.state["x"] = 100 + int((time.perf_counter() - t0) * 800) % 1500
            app.ov.update()
        m = app.ovl.moves
        return max((b - a for a, b in zip(m, m[1:])), default=1) * 1000, len(m)

    run(1.5)
    app.state["exe"] = "Last Epoch.exe"
    worst, n = run(2)
    assert app.active and n > 100
    assert worst < 60, f"khựng {worst:.0f} ms"
    assert not log_errors()


def test_stream_toggle(app):
    """Bật/tắt chế độ stream nhiều lần: trang OBS mở được, tắt thì đóng hẳn, không lỗi."""
    for _ in range(3):
        app.stream_var.set(True)
        app.set_stream()
        pump(app, 3)
        assert app.stream is not None and app.cfg["stream"] and app.ovl.target is app.stream
        assert "EventSource" in urllib.request.urlopen(app.stream.url, timeout=3).read().decode()
        url = app.stream.url
        app.stream_var.set(False)
        app.set_stream()
        pump(app, 3)
        assert app.stream is None and not app.cfg["stream"] and app.ovl.target is None
        with pytest.raises(OSError):
            urllib.request.urlopen(url, timeout=3)
    app.stream_var.set(True)
    app.set_stream()
    app.set_language("en")          # dòng cài đặt dựng lại được ở tiếng Anh, máy chủ vẫn chạy
    pump(app)
    assert app.stream is not None
    assert not log_errors()


def test_follow_smooth_while_stream_watched(app):
    """Stream bật, OBS đang xem, con trỏ động + tìm con trỏ: con trỏ trên màn hình vẫn bám đều,
    và ảnh tìm con trỏ lên stream kèm đúng điểm click của nó."""
    app.stream_var.set(True)
    app.set_stream()
    app.hide_to_tray()
    app.state["exe"] = "Last Epoch.exe"          # hồ sơ LE: lấp lánh (khung động)
    pump(app, 30)
    assert app.active
    c = http.client.HTTPConnection("127.0.0.1", app.stream.port, timeout=5)
    c.request("GET", "/events")
    resp = c.getresponse()
    imgs = []

    def drain():                                  # như OBS: đọc liên tục
        try:
            while True:
                line = resp.fp.readline().decode()
                if not line:
                    return
                if line.startswith("data:") and '"png"' in line:
                    imgs.append(json.loads(line[5:]))
        except (OSError, ValueError):
            pass

    threading.Thread(target=drain, daemon=True).start()
    app.ovl.moves.clear()
    t0 = time.perf_counter()
    found = False
    while time.perf_counter() - t0 < 2:
        app.state["x"] = 100 + int((time.perf_counter() - t0) * 800) % 1500
        if not found and time.perf_counter() - t0 > 1:
            found = True
            app.start_find()
        app.ov.update()
    m = app.ovl.moves
    worst = max((b - a for a, b in zip(m, m[1:])), default=1) * 1000
    c.close()
    assert len(m) > 100 and worst < 60, f"{len(m)} lần dời, khựng {worst:.0f} ms"
    assert len({d["id"] for d in imgs}) > 3              # khung động lên stream
    normal = max(d["w"] for d in imgs if d["id"] == imgs[0]["id"])
    big = [d for d in imgs if d["w"] == d["h"] and d["w"] > 2 * normal]    # ảnh vòng sáng tìm con trỏ (~3,6 lần)
    assert big and all((d["hx"], d["hy"]) == (d["w"] // 2, d["h"] // 2) for d in big)
    assert not log_errors()


@pytest.mark.skipif(sys.platform != "win32", reason="đo bằng font thật của Windows")
def test_options_tab_fits_window(app):
    """Cửa sổ cố định 1000x700: tab Tùy chọn (cả khi chế độ stream bật, cả tiếng Anh) không được tràn."""
    for lang in ("vi", "en"):
        app.set_language(lang)
        pump(app)
        app.show_tab("opts")
        for on in (False, True):
            app.stream_var.set(on)
            app.set_stream()
            pump(app, 5)
            need, have = app.pages["opts"].winfo_reqheight(), app.content.winfo_height()
            assert need <= have, f"{lang} stream={on}: cần {need} px, chỉ có {have} px"


def test_follow_runs_while_ui_busy(app):
    """Luồng giao diện bận (dựng ảnh, đổi tab...) không cập nhật Tk thì con trỏ vẫn bám chuột (luồng riêng)."""
    app.hide_to_tray()
    app.state["exe"] = "Last Epoch.exe"
    pump(app)
    assert app.active and app.follow.on
    app.ovl.moves.clear()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.3:
        app.state["x"] = 100 + int((time.perf_counter() - t0) * 800) % 1500
        sum(i * i for i in range(2000))          # việc nặng trên luồng giao diện, không gọi ov.update()
    m = app.ovl.moves
    worst = max((b - a for a, b in zip(m, m[1:])), default=1) * 1000
    assert len(m) > 50 and worst < 30, f"{len(m)} lần dời, khựng {worst:.0f} ms"
    app.enabled = False
    pump(app)
    assert not app.active and not app.follow.on
    assert not log_errors()

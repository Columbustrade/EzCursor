"""Kiểm thử giao diện và vòng lặp bám chuột với Windows giả lập (chạy dưới xvfb trên Linux)."""
import json
import os
import re
import shutil
import time

import pytest

from harness import ez

AD = os.path.join(os.environ["APPDATA"], "EzCursor")


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

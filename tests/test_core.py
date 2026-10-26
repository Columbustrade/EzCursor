"""Kiểm thử phần lõi (không cần giao diện)."""
import io
import json
import struct

from PIL import Image, ImageDraw

from harness import ez


def _tri(color, size=32):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(0, 0), (0, size - 1), (size - 1, size // 2)], fill=color)
    return im


def _cur_bytes(im, hot):
    b = io.BytesIO()
    im.save(b, format="ICO", sizes=[im.size])
    d = bytearray(b.getvalue())
    d[2] = 2
    struct.pack_into("<HH", d, 10, *hot)
    return bytes(d)


def test_version_and_paths():
    assert ez.APP_NAME == "EzCursor"
    assert ez.ENTRY_SCRIPT.name == "ezcursor.py" and ez.ENTRY_SCRIPT.exists()
    assert ez.res_path("ezc").is_dir()


def test_default_cfg_is_deep_copy():
    a, b = ez.default_cfg(), ez.default_cfg()
    a["hotkeys"]["toggle"]["mods"].append("shift")
    assert b["hotkeys"] == ez.DEFAULT_CFG["hotkeys"]
    assert a["color"] == "#ff2828" and a["predict"] is True and a["keep_taskbar"] is True


def test_load_cfg_repairs_bad_values(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"size": "big", "shape": "khong-co", "hotkeys": "x", "setup_done": True}), encoding="utf-8")
    import ezc.config as config
    monkeypatch.setattr(config, "CONFIG_PATH", p)
    cfg = config.load_cfg()
    assert cfg["shape"] == ez.DEFAULT_CFG["shape"]
    assert cfg["hotkeys"] == ez.DEFAULT_CFG["hotkeys"]


def test_hotkeys():
    hk = ez.DEFAULT_CFG["hotkeys"]
    assert ez.hotkey_parts(hk["toggle"], "toggle") == ["Ctrl", "Alt", "H"]
    assert ez.hotkey_parts(hk["color"], "color")[-1] == "1–5"
    bad = {"toggle": {"mods": ["shift"], "vk": 72}, "shape": {"mods": ["ctrl"], "vk": 9999}, "quit": "x"}
    assert ez.clean_hotkeys(bad) == hk
    assert [ez.vk_name(v) for v in (0x41, 0x35, 0x70, 0x63, 0x20)] == ["A", "5", "F1", "Num3", "Space"]


def test_cursor_files(tmp_path):
    for size in (32, 64):
        f = tmp_path / f"t{size}.cur"
        f.write_bytes(_cur_bytes(_tri("red", size), (3, 5)))
        frames, hot, steps = ez.load_cursor_file(str(f))
        assert frames[0].size == (size, size) and frames[0].mode == "RGBA" and hot == (3, 5)
    gif = [_tri(c, 40) for c in ("red", "lime", "blue")]
    g = tmp_path / "t.gif"
    gif[0].save(g, save_all=True, append_images=gif[1:], duration=[50, 120, 200], loop=0, disposal=2)
    frames, hot, steps = ez.load_cursor_file(str(g))
    assert len(frames) == 3


def test_png_to_cur_roundtrip(tmp_path):
    im = _tri("#22D3EE", 48)
    f = tmp_path / "x.cur"
    f.write_bytes(ez.png_to_cur(im, (2, 7)))
    frames, hot, _ = ez.load_cursor_file(str(f))
    assert frames[0].size == (48, 48) and hot == (2, 7)


def test_maker_renders_every_shape():
    for code, _name, kind in ez.MAKER_SHAPES:
        spec = dict(ez.MAKER_DEFAULT, shape=code, **ez.MAKER_SHAPE_DEFAULTS.get(code, {}))
        im, hot = ez.maker_render(spec, 128)
        assert im.size == (128, 128) and im.getbbox() is not None, code
        assert 0 <= hot[0] < 128 and 0 <= hot[1] < 128, code


def test_ombre():
    im, hot = ez.render_shape("Mũi tên", "#ff2828", 64, None, "Giữa ảnh")
    tmap = ez.ombre_tmap(im, hot)
    for code, _name, colors in ez.OMBRE_PRESETS:
        lut = ez.ombre_lut(colors)
        out = ez.apply_ombre(im, tmap, lut)
        assert out.size == im.size and out.mode == "RGBA"
    assert set(ez.OMBRE_SPEEDS) == {"slow", "mid", "fast"}


def test_builtin_shapes_render():
    for shape in ("Mũi tên", "Vòng tròn", "Dấu thập", "Chấm tròn", "Kim cương"):
        im, hot = ez.render_shape(shape, "#22D3EE", 48, None, "Giữa ảnh")
        assert im.getbbox() is not None, shape

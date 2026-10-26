"""Bộ con trỏ Bibata đi kèm."""

import json

from PIL import Image, ImageChops

from .base import res_path
from .colors import _rgb, luminance, tint_image


BIBATA_THEMES = {
    "amber": ("Amber", "#FF8300", "#FFFFFF", "#001524"),
    "classic": ("Classic", "#000000", "#FFFFFF", "#000000"),
    "ice": ("Ice", "#FFFFFF", "#000000", "#FFFFFF"),
}
BIBATA_CURSORS = [
    ("left_ptr", "Mũi tên"), ("right_ptr", "Mũi tên ngược"), ("center_ptr", "Mũi tên đứng"),
    ("hand2", "Bàn tay chỉ"), ("hand1", "Bàn tay mở"), ("grabbing", "Nắm tay"),
    ("crosshair", "Tâm ngắm"), ("cross", "Dấu thập"), ("tcross", "Thập mảnh"),
    ("plus", "Dấu cộng"), ("dotbox", "Ô chấm"), ("X_cursor", "Dấu X"), ("pencil", "Bút chì"),
]


def bibata_colors(theme, custom_color):
    if theme in BIBATA_THEMES:
        return BIBATA_THEMES[theme][1:]
    outline = "#000000" if luminance(custom_color) > 170 else "#FFFFFF"
    return custom_color, outline, "#001524" if outline == "#FFFFFF" else "#FFFFFF"


_bib_cache = {}


def bibata_image(base_dir, variant, name, colors):
    """Ảnh con trỏ Bibata 256px đã tô màu (thân, viền, phụ)."""
    key = (variant, name, colors)
    if key in _bib_cache:
        return _bib_cache[key]
    src = Image.open(base_dir / variant / f"{name}.png").convert("RGBA")
    r, g, b, a = src.split()
    base, outline, accent = (_rgb(c) for c in colors)
    chans = []
    for k in range(3):
        layer = ImageChops.add(ImageChops.add(g.point(lambda v, f=base[k]: v * f // 255),
                                              b.point(lambda v, f=outline[k]: v * f // 255)),
                               r.point(lambda v, f=accent[k]: v * f // 255))
        chans.append(layer)
    out = Image.merge("RGBA", (*chans, a))
    fixed = base_dir / variant / f"{name}.fixed.png"
    if fixed.exists():
        out.alpha_composite(Image.open(fixed).convert("RGBA"))
    if len(_bib_cache) > 64:
        _bib_cache.clear()
    _bib_cache[key] = out
    return out


BIBATA_DIR = res_path("bibata")
# Con trỏ riêng của EzCursor: (mã hình, tên hiển thị, file ảnh 256 px, điểm click, màu quầng sáng)
OWN_CURSORS = [
    ("EzDrop", "Liquid Drop", "ezdrop.png", (21, 20), "#FF2E93"),
    ("EzPink", "Mảnh hồng", "ezpink.png", (25, 21), "#FF2E93"),
    # Bộ EzCursor phong cách game (1.8.0)
    ("ez_crosshair", "Tâm ngắm Neon", "ez/ez_crosshair.png", (128, 128), "#3B7BF9"),
    ("ez_sword", "Mũi kiếm", "ez/ez_sword.png", (26, 26), "#3B7BF9"),
    ("ez_crystal", "Mũi tên Pha lê", "ez/ez_crystal.png", (24, 24), "#3B7BF9"),
    ("ez_gem", "Viên ngọc", "ez/ez_gem.png", (26, 26), "#3B7BF9"),
    ("ez_rune", "Ký tự Rune", "ez/ez_rune.png", (128, 128), "#3B7BF9"),
    ("ez_orb", "Cầu năng lượng", "ez/ez_orb.png", (128, 128), "#3B7BF9"),
    ("ez_flame", "Ngọn lửa", "ez/ez_flame.png", (24, 24), "#3B7BF9"),
    ("ez_spear", "Mũi giáo", "ez/ez_spear.png", (24, 24), "#3B7BF9"),
    ("ez_feather", "Lông vũ", "ez/ez_feather.png", (24, 24), "#3B7BF9"),
    ("ez_star", "Ngôi sao", "ez/ez_star.png", (128, 128), "#3B7BF9"),
    ("ez_shot", "Mũi tên Bắn", "ez/ez_shot.png", (24, 24), "#3B7BF9"),
    ("ez_neon", "Mũi tên Neon", "ez/ez_neon.png", (24, 24), "#3B7BF9"),
]
OWN_BY_ID = {c[0]: c for c in OWN_CURSORS}
_own_imgs = {}


def own_image(shape):
    if shape not in OWN_BY_ID:
        return None
    if shape not in _own_imgs:
        try:
            _own_imgs[shape] = Image.open(res_path("assets", OWN_BY_ID[shape][2])).convert("RGBA")
        except Exception:
            _own_imgs[shape] = None
    return _own_imgs[shape]


_own_tinted = {}


def own_image_colored(shape, color):
    """Con trỏ EzCursor đổi sang màu đã chọn (giữ phần trắng/đen), có cache."""
    key = (shape, color.lower())
    if key not in _own_tinted:
        base = own_image(shape)
        if base is None:
            return None
        if len(_own_tinted) > 40:
            _own_tinted.clear()
        _own_tinted[key] = tint_image(base, color)
    return _own_tinted[key]


try:
    BIBATA_META = json.loads((BIBATA_DIR / "bibata.json").read_text(encoding="utf-8"))
except Exception:
    BIBATA_META = {"hotspots": {}}

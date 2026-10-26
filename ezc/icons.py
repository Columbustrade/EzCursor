"""Biểu tượng vẽ bằng mã: sao, menu, logo."""

import math

from PIL import Image, ImageDraw

from .base import res_path
from .theme import ACCENT, SIDEBAR


STAR_PTS = [(0, -1), (0.14, -0.29), (0.29, -0.14), (1, 0), (0.29, 0.14), (0.14, 0.29),
            (0, 1), (-0.14, 0.29), (-0.29, 0.14), (-1, 0), (-0.29, -0.14), (-0.14, -0.29)]


def _ss(draw_fn, size, scale=4):
    im = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), scale)
    return im.resize((size, size), Image.LANCZOS)


def star_icon(filled, color, size=16):
    def draw(d, s):
        k = s * size / 16
        pts = []
        for i in range(10):
            r = (7.2 if i % 2 == 0 else 3.1) * k
            a = math.pi / 2 + i * math.pi / 5
            pts.append((8 * k + r * math.cos(a), 8.6 * k - r * math.sin(a)))
        if filled:
            d.polygon(pts, fill=color)
        else:
            d.line(pts + [pts[0]], fill=color, width=max(1, int(1.4 * k)), joint="curve")
    return _ss(draw, size)


def nav_icon(kind, color, size=20):
    def draw(d, s):
        s = s * size / 20          # icon thiết kế trên lưới 20 đơn vị
        w = int(2 * s)
        if kind == "cursor":
            d.line([(4 * s, 3 * s), (17 * s, 9.5 * s), (11 * s, 11 * s), (9.5 * s, 17 * s), (4 * s, 3 * s)],
                   fill=color, width=w, joint="curve")
        elif kind == "apps":
            d.rounded_rectangle([2.5 * s, 6 * s, 17.5 * s, 15 * s], radius=3.5 * s, outline=color, width=w)
            d.line([(7 * s, 8.5 * s), (7 * s, 12.5 * s)], fill=color, width=w)
            d.line([(5 * s, 10.5 * s), (9 * s, 10.5 * s)], fill=color, width=w)
            for cx, cy in ((13 * s, 9.5 * s), (14.8 * s, 11.6 * s)):
                d.ellipse([cx - 1.1 * s, cy - 1.1 * s, cx + 1.1 * s, cy + 1.1 * s], fill=color)
        elif kind == "fx":
            c = 10 * s
            r = 8.5 * s
            d.polygon([(c + x * r, c + y * r) for x, y in STAR_PTS], outline=color, width=int(1.8 * s))
            d.ellipse([15 * s, 2 * s, 18.4 * s, 5.4 * s], fill=color)
        elif kind == "library":
            for x0, y0 in ((3, 3), (11, 3), (3, 11), (11, 11)):
                d.rounded_rectangle([x0 * s, y0 * s, (x0 + 6) * s, (y0 + 6) * s], radius=1.6 * s,
                                    outline=color, width=w)
        else:  # tùy chọn
            d.line([(3 * s, 6 * s), (17 * s, 6 * s)], fill=color, width=w)
            d.line([(3 * s, 14 * s), (17 * s, 14 * s)], fill=color, width=w)
            for cx, cy in ((7.5 * s, 6 * s), (12.5 * s, 14 * s)):
                d.ellipse([cx - 2.4 * s, cy - 2.4 * s, cx + 2.4 * s, cy + 2.4 * s], fill=SIDEBAR, outline=color, width=w)
    return _ss(draw, size)


_logo_frames = None


def logo_frames():
    """Danh sách khung hình logo động (ảnh vuông) từ assets/logo_anim.png."""
    global _logo_frames
    if _logo_frames is None:
        try:
            sheet = Image.open(res_path("assets", "logo_anim.png")).convert("RGBA")
            f = sheet.height
            _logo_frames = [sheet.crop((i * f, 0, (i + 1) * f, f)) for i in range(sheet.width // f)]
        except Exception:
            _logo_frames = []
    return _logo_frames


def logo_image(size=26):
    try:
        return Image.open(res_path("logo.png")).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        pass
    def draw(d, s):
        pts = [(2 * s, 1.5 * s), (24 * s, 13 * s), (24 * s, 24 * s), (13 * s, 24 * s)]
        d.polygon(pts, fill=ACCENT)
        d.line(pts + [pts[0]], fill="#FFFFFF", width=int(2.2 * s), joint="curve")
    return _ss(draw, size)


def simple_icon(kind, color, size=16):
    def draw(d, s):
        s = s * size / 16          # icon thiết kế trên lưới 16 đơn vị
        w = int(2 * s)
        if kind == "trash":
            w = max(1, int(1.6 * s))
            d.line([(3 * s, 4.5 * s), (13 * s, 4.5 * s)], fill=color, width=w)
            d.line([(6.5 * s, 4.5 * s), (6.5 * s, 2.5 * s), (9.5 * s, 2.5 * s), (9.5 * s, 4.5 * s)], fill=color, width=w)
            d.polygon([(4.5 * s, 6 * s), (11.5 * s, 6 * s), (10.8 * s, 14 * s), (5.2 * s, 14 * s)], outline=color, width=w)
            return
        if kind == "upload":
            d.line([(8 * s, 11 * s), (8 * s, 2.5 * s)], fill=color, width=w)
            d.line([(4.5 * s, 6 * s), (8 * s, 2.5 * s), (11.5 * s, 6 * s)], fill=color, width=w, joint="curve")
            d.line([(2.5 * s, 10.5 * s), (2.5 * s, 13.5 * s), (13.5 * s, 13.5 * s), (13.5 * s, 10.5 * s)],
                   fill=color, width=w, joint="curve")
        elif kind == "refresh":
            d.arc([2.5 * s, 2.5 * s, 13.5 * s, 13.5 * s], start=-40, end=280, fill=color, width=w)
            d.line([(13.8 * s, 2 * s), (13.8 * s, 6.2 * s), (9.6 * s, 6.2 * s)], fill=color, width=w, joint="curve")
        elif kind == "plus":
            d.line([(8 * s, 3 * s), (8 * s, 13 * s)], fill=color, width=w)
            d.line([(3 * s, 8 * s), (13 * s, 8 * s)], fill=color, width=w)
    return _ss(draw, size)

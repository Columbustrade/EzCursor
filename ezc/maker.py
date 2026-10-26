"""Trình tạo con trỏ: vẽ con trỏ từ hình dạng, màu và viền."""

import io
import math
import struct

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .colors import _rgb, mix
from .ombre import ombre_lut, ombre_tmap


MAKER_SHAPES = [   # (mã, tên, loại: "poly" có mũi / "center" điểm click ở giữa)
    ("arrow", "Nhọn", "poly"), ("arrow_round", "Bo tròn", "poly"),
    ("arrow_slim", "Mảnh", "poly"), ("shard", "Pha lê", "poly"), ("drop", "Giọt nước", "poly"),
    ("triangle", "Tam giác", "poly"), ("diamond", "Kim cương", "center"), ("dot", "Chấm", "center"),
    ("ring", "Vòng", "center"), ("cross", "Tâm ngắm", "center"),
]
MAKER_SHAPE_DEFAULTS = {   # thông số hợp lý khi đổi sang hình đó
    "arrow": {"width": 1.0, "tail": 1.0, "round": 0.0}, "arrow_round": {"width": 1.0, "tail": 1.0, "round": 0.6},
    "arrow_slim": {"width": 0.9, "tail": 1.0, "round": 0.0}, "shard": {"width": 1.0, "tail": 0.6, "round": 0.0},
    "drop": {"width": 1.0, "tail": 0.6, "round": 0.0}, "triangle": {"width": 1.0, "tail": 0.5, "round": 0.2},
    "diamond": {"width": 0.8, "round": 0.0}, "dot": {"width": 0.5}, "ring": {"width": 0.9, "thick": 0.25},
    "cross": {"width": 1.0, "tail": 0.35, "thick": 0.35},
}
MAKER_DEFAULT = {"shape": "arrow", "width": 1.0, "tail": 1.0, "round": 0.0, "rot": 0, "thick": 0.5,
                 "fill": "solid", "color": "#FF2E93", "ombre": ["#FF2E93", "#FF8A3D", "#FFD60A"],
                 "in_col": "#FFFFFF", "in_w": 7, "out_col": "#0B0D12", "out_w": 4,
                 "tip": True, "shine": True, "shadow": True, "hot": None}


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _maker_poly(sp):
    """Đa giác (đơn vị, mũi ở gốc tọa độ) của các hình có mũi."""
    w, t = sp["width"], sp["tail"]
    sh = sp["shape"]
    if sh in ("arrow", "arrow_round", "arrow_slim"):
        if sh == "arrow_slim":
            base = [(0, 0), (0.04, 0.92), (0.22, 0.70), (0.34, 1.02), (0.43, 0.98), (0.31, 0.66), (0.58, 0.66)]
        else:
            base = [(0, 0), (0, 0.86), (0.22, 0.66), (0.36, 0.98), (0.49, 0.93), (0.35, 0.62), (0.63, 0.62)]
        notch_l, notch_r = base[2], base[5]
        out = []
        for i, (x, y) in enumerate(base):
            if i in (3, 4):                      # đuôi: co giãn theo "Độ dài đuôi"
                nx, ny = (notch_l if i == 3 else notch_r)
                x, y = nx + (x - nx) * t, ny + (y - ny) * t
            out.append((x * w, y))
        return out, -15
    if sh == "shard":   # cánh diều đối xứng theo trục, xoay -45° để mũi ở góc trên trái
        return [(0, 0), (0.24 * w, 0.62), (0, 0.72 + 0.28 * t), (-0.24 * w, 0.62)], -45
    if sh == "drop":
        r = 0.30 * w
        cy = 0.55 + 0.25 * t
        pts = [(0, 0)] + [(r * math.cos(a / 32 * math.pi), cy + r * math.sin(a / 32 * math.pi)) for a in range(64)]
        h = _hull(pts)
        i = h.index((0, 0))
        return h[i:] + h[:i], -45
    if sh == "triangle":
        return [(0, 0), (0.42 * w, 0.62 + 0.3 * t), (-0.42 * w, 0.62 + 0.3 * t)], -45
    return [(0, 0)], 0


def _rot(pts, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(x * ca - y * sa, x * sa + y * ca) for x, y in pts]


def maker_render(sp, size=256):
    """Vẽ con trỏ theo thông số -> (ảnh RGBA size×size, điểm click)."""
    sp = dict(MAKER_DEFAULT, **sp)
    k = size / 256
    pad = (sp["in_w"] + sp["out_w"]) * k + (10 if sp["shadow"] else 4) * k + 4 * k
    SS = 4
    W = size * SS
    mask_hi = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(mask_hi)
    kind = dict((a, c) for a, _, c in MAKER_SHAPES).get(sp["shape"], "poly")
    if kind == "poly":
        pts, base_rot = _maker_poly(sp)
        pts = _rot(pts, base_rot + sp["rot"])          # điểm đầu tiên luôn là mũi
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
        sc = (size - 2 * pad) / span
        ox, oy = pad - min(xs) * sc, pad - min(ys) * sc
        # căn giữa phần dư theo chiều ngắn
        ox += ((size - 2 * pad) - (max(xs) - min(xs)) * sc) / 2 * 0.0
        poly = [((x * sc + ox) * SS, (y * sc + oy) * SS) for x, y in pts]
        d.polygon(poly, fill=255)
        hot = (pts[0][0] * sc + ox, pts[0][1] * sc + oy)
    else:
        c = W / 2
        R = (size / 2 - pad) * SS * min(1.0, 0.55 + 0.45 * sp["width"])
        th = max(2 * SS * k, R * (0.08 + 0.30 * sp["thick"]))
        if sp["shape"] == "dot":
            d.ellipse([c - R * 0.7, c - R * 0.7, c + R * 0.7, c + R * 0.7], fill=255)
        elif sp["shape"] == "ring":
            d.ellipse([c - R, c - R, c + R, c + R], fill=255)
            d.ellipse([c - R + th, c - R + th, c + R - th, c + R - th], fill=0)
        elif sp["shape"] == "diamond":
            rx = R * (0.55 + 0.45 * sp["width"]) / 1.0
            pts = _rot([(0, -R), (rx * 0.8, 0), (0, R), (-rx * 0.8, 0)], sp["rot"])
            d.polygon([(c + x, c + y) for x, y in pts], fill=255)
        else:   # tâm ngắm: 4 thanh có khe hở
            gap = R * (0.15 + 0.35 * sp["tail"])
            h = th / 2
            for ang in (0, 90, 180, 270):
                bar = _rot([(gap, -h), (R, -h), (R, h), (gap, h)], ang + sp["rot"])
                d.polygon([(c + x, c + y) for x, y in bar], fill=255)
        hot = (size / 2, size / 2)
    mask = mask_hi.resize((size, size), Image.LANCZOS)
    if sp["round"] > 0:                                  # bo góc: làm mờ rồi cắt ngưỡng
        r = 1 + sp["round"] * 10 * k
        mask = mask.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 0 if v < 118 else (255 if v > 138 else (v - 118) * 255 // 20))

    def grow(m, w):
        w = int(round(w * k))
        if w <= 0:
            return m
        g = m.filter(ImageFilter.MaxFilter(2 * w + 1))
        return g.filter(ImageFilter.GaussianBlur(0.6))

    m_in = grow(mask, sp["in_w"])
    m_out = grow(m_in, sp["out_w"])
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if sp["shadow"]:
        sh = m_out.filter(ImageFilter.GaussianBlur(5 * k))
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        layer.putalpha(sh.point(lambda v: v * 110 // 255))
        out.alpha_composite(layer, (int(3 * k), int(5 * k)))
    for m, col in ((m_out, sp["out_col"]), (m_in, sp["in_col"])):
        layer = Image.new("RGBA", (size, size), _rgb(col) + (0,))
        layer.putalpha(m)
        out.alpha_composite(layer)
    # thân
    if sp["fill"] == "ombre":
        tm = ombre_tmap(Image.merge("RGBA", (mask, mask, mask, mask)), hot)
        lut = ombre_lut(sp["ombre"])
        body = Image.merge("RGB", [tm.point(ch) for ch in lut]).convert("RGBA")
        body.putalpha(mask)
    else:
        body = Image.new("RGBA", (size, size), _rgb(sp["color"]) + (0,))
        if sp["fill"] == "glass":
            body.putalpha(mask.point(lambda v: v * 150 // 255))
        else:
            body.putalpha(mask)
    if sp["fill"] == "glass":   # lõi trong suốt: xóa phần viền trong phía sau để thấy nền
        inner = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out = Image.composite(inner, out, mask)
    out.alpha_composite(body)
    if sp["shine"]:            # vệt sáng dọc cạnh trên trái
        sh_off = ImageChops.offset(mask, int(6 * k), int(6 * k))
        shine = ImageChops.subtract(mask, sh_off).filter(ImageFilter.GaussianBlur(1.2 * k))
        shine = ImageChops.multiply(shine, mask.filter(ImageFilter.MinFilter(3)))
        layer = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        layer.putalpha(shine.point(lambda v: v * 150 // 255))
        out.alpha_composite(layer)
    if sp["tip"]:
        hx, hy = hot
        r = 7 * k
        tip_col = sp["ombre"][0] if sp["fill"] == "ombre" else sp["color"]
        layer = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
        dd = ImageDraw.Draw(layer)
        dd.ellipse([(hx - r - 2.5 * k) * SS, (hy - r - 2.5 * k) * SS, (hx + r + 2.5 * k) * SS, (hy + r + 2.5 * k) * SS],
                   fill="#FFFFFF")
        dd.ellipse([(hx - r) * SS, (hy - r) * SS, (hx + r) * SS, (hy + r) * SS], fill=mix(tip_col, "#FFFFFF", 0.25))
        out.alpha_composite(layer.resize((size, size), Image.LANCZOS))
    if sp.get("hot"):
        hot = tuple(sp["hot"])
    return out, (int(round(hot[0])), int(round(hot[1])))


def png_to_cur(im, hot):
    """File .cur một ảnh, dữ liệu ảnh là PNG (Windows Vista trở lên đọc được)."""
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    w, h = im.size
    return struct.pack("<HHH", 0, 2, 1) + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hot[0], hot[1],
                                                       len(png), 22) + png

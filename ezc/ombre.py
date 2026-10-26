"""Màu ombre (chuyển sắc từ mũi ra đuôi con trỏ)."""

import math

from PIL import Image, ImageChops, ImageDraw

from .colors import _rgb


OMBRE_PRESETS = [   # (mã, tên, các màu từ mũi ra đuôi)
    ("sunset", "Hoàng hôn", ["#FF2E93", "#FF8A3D", "#FFD60A"]),
    ("ez", "EzCursor", ["#2EE59D", "#2F80FF", "#FF2E93"]),
    ("ocean", "Đại dương", ["#22D3EE", "#3B7BF9", "#8B5CF6"]),
    ("fire", "Lửa", ["#FFD60A", "#FF6A00", "#E01E37"]),
    ("toxic", "Độc dược", ["#E4FF3B", "#7CF03B", "#14B8A6"]),
    ("frost", "Băng giá", ["#E0F7FF", "#7DD3FC", "#3B82F6"]),
    ("void", "Hư không", ["#F0ABFC", "#A855F7", "#4C1D95"]),
    ("rainbow", "Cầu vồng", ["#FF3B3B", "#FFD60A", "#2EE59D", "#22D3EE", "#A855F7"]),
]
OMBRE_FRAMES = 24


_tmap_cache = {}


def ombre_tmap(im, hot):
    """Ảnh xám: 0 ở điểm click, 255 ở phần xa nhất (đuôi). Điểm click ở giữa thì chuyển chéo."""
    key = (im.size, tuple(hot), hash(im.getchannel("A").tobytes()))
    if key not in _tmap_cache:
        if len(_tmap_cache) > 64:
            _tmap_cache.clear()
        _tmap_cache[key] = _ombre_tmap(im, hot)
    return _tmap_cache[key]


def _ombre_tmap(im, hot):
    w, h = im.size
    bb = im.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox() or (0, 0, w, h)
    hx, hy = hot
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    if math.hypot(cx - hx, cy - hy) < 0.18 * max(bb[2] - bb[0], bb[3] - bb[1], 1):
        hx, hy = bb[0], bb[1]                         # con trỏ tâm (tâm ngắm, vòng tròn): góc trên trái -> dưới phải
    dx, dy = cx - hx, cy - hy
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    m = max((x - hx) * dx + (y - hy) * dy for x in (bb[0], bb[2]) for y in (bb[1], bb[3])) or 1.0
    k = 255.0 / m
    data = [max(0, min(255, int(((x + 0.5 - hx) * dx + (y + 0.5 - hy) * dy) * k)))
            for y in range(h) for x in range(w)]
    t = Image.new("L", (w, h))
    t.putdata(data)
    return t


_ombre_luts = {}


def ombre_lut(colors, phase=0.0, anim=False):
    """Bảng 256 màu cho từng kênh R, G, B. Chuyển động: dải màu đi qua lại, nối liền khi lặp."""
    key = (tuple(colors), round(phase, 4), anim)
    if key in _ombre_luts:
        return _ombre_luts[key]
    stops = [_rgb(c) for c in colors]
    if anim:
        stops = stops + stops[-2::-1]
    n = len(stops) - 1
    out = ([], [], [])
    for i in range(256):
        u = i / 255
        if anim:
            u = (u * 0.5 + phase) % 1.0
        pos = u * n
        j = min(int(pos), n - 1)
        f = pos - j
        for ch in range(3):
            out[ch].append(int(stops[j][ch] + (stops[j + 1][ch] - stops[j][ch]) * f))
    if len(_ombre_luts) > 200:
        _ombre_luts.clear()
    _ombre_luts[key] = out
    return out


def apply_ombre(im, tmap, lut):
    """Tô dải màu lên phần có màu của ảnh, giữ phần trắng/đen và độ sáng tối (bóng, điểm sáng)."""
    g = Image.merge("RGB", [tmap.point(ch) for ch in lut])
    gh, gs, gv = g.convert("HSV").split()
    rgb = im.convert("RGB")
    _h, sat, val = rgb.convert("HSV").split()
    mask = sat.point(lambda x: max(0, min(255, (x - 40) * 4)))
    ns = ImageChops.multiply(sat.point(lambda x: min(255, int(x * 1.3))), gs)
    nv = ImageChops.multiply(val.point(lambda x: min(255, 60 + x)), gv)
    colored = Image.merge("HSV", (gh, ns, nv)).convert("RGB")
    out = Image.composite(colored, rgb, mask)
    out.putalpha(im.getchannel("A"))
    return out


def ombre_dot(colors, selected, size=30):
    """Ô tròn dải màu (có vòng trắng khi đang chọn); colors=None: ô "+" tự chọn."""
    k = 4
    W = size * k
    out = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    if colors is None:
        d.ellipse([k, k, W - k - 1, W - k - 1], outline="#4A5266", width=k)
        m, t = W // 2, W // 7
        d.line([(m - t, m), (m + t, m)], fill="#9AA3B8", width=int(1.6 * k))
        d.line([(m, m - t), (m, m + t)], fill="#9AA3B8", width=int(1.6 * k))
        return out.resize((size, size), Image.LANCZOS)
    inset = 5 * k if selected else 2 * k
    sw = ombre_swatch(colors, (W - 2 * inset) // k).resize((W - 2 * inset, W - 2 * inset), Image.LANCZOS)
    out.alpha_composite(sw, (inset, inset))
    if selected:
        d.ellipse([k, k, W - k - 1, W - k - 1], outline="#FFFFFF", width=int(1.8 * k))
    return out.resize((size, size), Image.LANCZOS)


def ombre_swatch(colors, size=32, round_=True):
    """Ô tròn (hoặc thanh) dải màu để hiện trên nút."""
    w, h = (size, size) if round_ else (size * 4, size)
    bar = Image.new("RGB", (256, 1))
    lut = ombre_lut(colors)
    bar.putdata([(lut[0][i], lut[1][i], lut[2][i]) for i in range(256)])
    bar = bar.resize((w * 4, h * 4), Image.BILINEAR)
    if round_:
        bar = bar.rotate(-45, resample=Image.BICUBIC, expand=False, fillcolor=_rgb(colors[-1]))
    mask = Image.new("L", (w * 4, h * 4), 0)
    d = ImageDraw.Draw(mask)
    if round_:
        d.ellipse([2, 2, w * 4 - 3, h * 4 - 3], fill=255)
    else:
        d.rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=h * 2, fill=255)
    out = bar.convert("RGBA")
    out.putalpha(mask)
    return out.resize((w, h), Image.LANCZOS)

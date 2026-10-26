"""Tiện ích màu và tô màu ảnh."""

import colorsys

from PIL import Image


def tint_image(im, color):
    """Đổi phần có màu của ảnh sang màu đã chọn, giữ nguyên phần trắng/đen/xám."""
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    th, ts, tv = colorsys.rgb_to_hsv(r, g, b)
    alpha = im.getchannel("A")
    rgb = im.convert("RGB")
    h, s, v = rgb.convert("HSV").split()
    mask = s.point(lambda x: 255 if x > 70 else 0)          # chỉ đổi pixel có màu
    nh = Image.new("L", im.size, int(th * 255))
    ns = s.point(lambda x: int(x * ts))
    nv = v.point(lambda x: int(x * tv))
    colored = Image.merge("HSV", (nh, ns, nv)).convert("RGB")
    out = Image.composite(colored, rgb, mask)
    out.putalpha(alpha)
    return out


def mix(c1, c2, t):
    """Trộn màu c1 với c2 theo tỉ lệ t (0 = c1, 1 = c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def luminance(c):
    r, g, b = _rgb(c)
    return 0.299 * r + 0.587 * g + 0.114 * b

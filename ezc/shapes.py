"""Vẽ các hình con trỏ có sẵn."""

from PIL import Image, ImageDraw


def render_shape(shape, color, size, img_rgba, hotspot, file_hot=None):
    """Vẽ con trỏ (khử răng cưa), trả về (ảnh RGBA, điểm click)."""
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = n / 64

    def P(pts):
        return [(x * k, y * k) for x, y in pts]

    def W(v):
        return max(1, int(v * k))

    if shape == "Ảnh tải lên" and img_rgba is None:
        shape = "Vòng tròn"
    if shape == "Mũi tên":
        d.polygon(P([(3, 3), (3, 50), (15, 38), (23, 57), (31, 53), (23, 36), (40, 36)]),
                  fill=color, outline="#000000", width=W(2.5))
    elif shape == "Vòng tròn":
        d.ellipse([2.5 * k, 2.5 * k, 61.5 * k, 61.5 * k], outline="#000000", width=W(7))
        d.ellipse([4 * k, 4 * k, 60 * k, 60 * k], outline=color, width=W(4))
        d.ellipse([28 * k, 28 * k, 36 * k, 36 * k], fill=color, outline="#000000", width=W(2))
    elif shape == "Dấu thập":
        segs = [((32, 4), (32, 24)), ((32, 40), (32, 60)), ((4, 32), (24, 32)), ((40, 32), (60, 32))]
        for a, b in segs:
            d.line(P([a, b]), fill="#000000", width=W(7))
        for a, b in segs:
            d.line(P([a, b]), fill=color, width=W(3))
        d.ellipse([29 * k, 29 * k, 35 * k, 35 * k], fill=color, outline="#000000", width=W(1.5))
    elif shape == "Chấm tròn":
        d.ellipse([21 * k, 21 * k, 43 * k, 43 * k], fill=color, outline="#000000", width=W(3))
    elif shape == "Kim cương":
        d.polygon(P([(32, 6), (58, 32), (32, 58), (6, 32)]), fill=color, outline="#000000", width=W(3))
        d.ellipse([29 * k, 29 * k, 35 * k, 35 * k], fill="#000000")
    elif shape == "Ảnh tải lên":
        w, h = img_rgba.size
        f = n / max(w, h)
        pic = img_rgba.resize((max(1, round(w * f)), max(1, round(h * f))), Image.LANCZOS)
        top_left = hotspot == "Góc trên trái" or (hotspot == "Theo file" and file_hot)
        pos = (0, 0) if top_left else ((n - pic.width) // 2, (n - pic.height) // 2)
        im.alpha_composite(pic, pos)
    im = im.resize((size, size), Image.LANCZOS)
    if shape == "Mũi tên":
        hot = (round(3 * size / 64), round(3 * size / 64))
    elif shape == "Ảnh tải lên" and hotspot == "Theo file" and file_hot:
        k2 = size / max(img_rgba.size)
        hot = (min(size - 1, round(file_hot[0] * k2)), min(size - 1, round(file_hot[1] * k2)))
    elif shape == "Ảnh tải lên" and hotspot == "Góc trên trái":
        hot = (0, 0)
    else:
        hot = (size // 2, size // 2)
    return im, hot

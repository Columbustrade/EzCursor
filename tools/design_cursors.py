"""Bộ con trỏ EzCursor phong cách game – vẽ bằng hình học, xuất PNG 256 px.
Cách dùng (chỉ khi thiết kế, không cần cho bản build): pip install numpy scipy pillow
    py -3.13 tools/design_cursors.py assets/ez
Thêm mẫu mới: viết hàm vẽ mới, thêm vào DESIGNS, rồi thêm dòng tương ứng vào OWN_CURSORS trong ezcursor.py.
Ngôn ngữ chung (theo Liquid Drop): thân gradient xanh ngọc → xanh dương → tím hồng, viền trắng dày,
viền tối mảnh ngoài cùng để nổi trên nền sáng, bóng đổ mềm, vệt bóng sáng, chấm xanh ngọc ở điểm click."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

K = 4                    # vẽ ở 1024 px rồi thu về 256 px
N = 256 * K
PAL = ["#B6F0E6", "#3B7BF9", "#8E46B8"]     # sáng → giữa → tối, lấy từ Liquid Drop
MINT = "#2EE59D"


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def P(pts):
    return [(x * K, y * K) for x, y in pts]


def blank():
    return Image.new("L", (N, N), 0)


def bez(p0, p1, p2, p3, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def chaikin(pts, it=3, closed=True):
    for _ in range(it):
        new = []
        n = len(pts)
        for i in range(n if closed else n - 1):
            p, q = pts[i], pts[(i + 1) % n]
            new += [(0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]),
                    (0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1])]
        pts = new
    return pts


class Axis:
    """Hệ trục dọc theo đường chéo: u từ đầu nhọn (trên trái) về đuôi, v vuông góc."""

    def __init__(self, tip=(24, 24), ang=45):
        self.t = tip
        a = math.radians(ang)
        self.a = (math.cos(a), math.sin(a))
        self.n = (math.sin(a), -math.cos(a))

    def __call__(self, u, v=0):
        return (self.t[0] + u * self.a[0] + v * self.n[0], self.t[1] + u * self.a[1] + v * self.n[1])

    def pts(self, uv):
        return [self(u, v) for u, v in uv]


def gradient(mask, pal, ang=45, span=None):
    """Tô gradient 3 màu dọc theo hướng ang trên vùng mask."""
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float32)
    a = math.radians(ang)
    proj = xs * math.cos(a) + ys * math.sin(a)
    m = np.array(mask) > 0
    if span is None:
        lo, hi = proj[m].min(), proj[m].max()
    else:
        lo, hi = span[0] * K * 1.414, span[1] * K * 1.414
    t = np.clip((proj - lo) / max(1, hi - lo), 0, 1)
    c = [np.array(rgb(x), np.float32) for x in pal]
    t3 = t[..., None]
    col = np.where(t3 < 0.5, c[0] + (c[1] - c[0]) * (t3 / 0.5), c[1] + (c[2] - c[1]) * ((t3 - 0.5) / 0.5))
    img = Image.fromarray(col.astype(np.uint8), "RGB").convert("RGBA")
    img.putalpha(mask)
    return img


def dilate(mask, r):
    """Nới vùng mask thêm r px (ở thang 1024), bo tròn, khử răng cưa."""
    m = np.array(mask) > 127
    dist = ndimage.distance_transform_edt(~m)
    a = np.clip(r + 0.5 - dist, 0, 1) * 255
    return Image.fromarray(a.astype(np.uint8), "L")


def solid(mask, color, alpha=255):
    img = Image.new("RGBA", (N, N), rgb(color) + (0,))
    img.putalpha(mask.point(lambda v: v * alpha // 255))
    return img


def frame(body_mask, outline=26, rim=6, shadow=True):
    """Các lớp nền: bóng đổ, viền tối, viền trắng."""
    out = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    white = dilate(body_mask, outline)
    if shadow:
        sh = dilate(body_mask, outline + rim).filter(ImageFilter.GaussianBlur(14))
        sh = sh.transform(sh.size, Image.AFFINE, (1, 0, -10, 0, 1, -16))
        out.alpha_composite(solid(sh, "#000000", 110))
    out.alpha_composite(solid(dilate(body_mask, outline + rim), "#0B0D12", 210))
    out.alpha_composite(solid(white, "#FFFFFF"))
    return out


def dot(img, c, r=26, color=MINT):
    d = ImageDraw.Draw(img)
    x, y = c[0] * K, c[1] * K
    d.ellipse([x - r - 7, y - r - 7, x + r + 7, y + r + 7], fill=(11, 13, 18, 255))
    d.ellipse([x - r, y - r, x + r, y + r], fill=rgb(color) + (255,))
    d.ellipse([x - r * 0.45, y - r * 0.6, x - r * 0.05, y - r * 0.2], fill=(255, 255, 255, 150))


def shine(img, pts, width=18, alpha=150):
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(layer).line(P(pts), fill=(255, 255, 255, alpha), width=width * K // 4, joint="curve")
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3)))


def mask_poly(pts):
    m = blank()
    ImageDraw.Draw(m).polygon(P(pts), fill=255)
    return m


def finish(img):
    return img.resize((256, 256), Image.LANCZOS)


# ------------------------------------------------------------------ các mẫu
def sword(pal):
    A = Axis((26, 26))
    blade = A.pts([(0, 0), (34, 16), (146, 21), (146, -21), (34, -16)])
    guard = A.pts([(146, 48), (168, 48), (168, -48), (146, -48)])
    grip = A.pts([(168, 12), (230, 12), (230, -12), (168, -12)])
    m = blank()
    d = ImageDraw.Draw(m)
    for poly in (blade, guard, grip):
        d.polygon(P(poly), fill=255)
    pc = A(250)
    d.ellipse([(pc[0] - 23) * K, (pc[1] - 23) * K, (pc[0] + 23) * K, (pc[1] + 23) * K], fill=255)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    # mặt lưỡi tối một nửa + rãnh giữa
    half = mask_poly(A.pts([(0, 0), (34, -16), (146, -21), (146, 0)]))
    img.alpha_composite(solid(half, "#06102A", 70))
    ImageDraw.Draw(img).line(P(A.pts([(40, 0), (136, 0)])), fill=(255, 255, 255, 130), width=5 * K)
    g = mask_poly(guard)
    img.alpha_composite(solid(g, "#0B0D12", 60))
    for u in (182, 198, 214):
        ImageDraw.Draw(img).line(P(A.pts([(u, 11), (u + 6, -11)])), fill=(11, 13, 18, 90), width=3 * K)
    shine(img, A.pts([(30, 9), (120, 15)]), 14, 140)
    dot(img, (26, 26), 22)
    return finish(img), (26, 26)


def crystal_arrow(pal):
    tip = (24, 24)
    pts = [tip, (24, 206), (72, 160), (110, 238), (148, 222), (112, 148), (180, 148)]
    m = mask_poly(pts)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    core = (78, 112)
    facets = [((24, 206), (72, 160), 0.30), ((72, 160), (112, 148), 0.0), ((112, 148), (180, 148), -0.22),
              ((180, 148), tip, 0.18), (tip, (24, 206), -0.12)]
    for a, b, k in facets:
        f = mask_poly([a, b, core])
        img.alpha_composite(solid(f, "#FFFFFF" if k > 0 else "#06102A", int(abs(k) * 255)))
    d = ImageDraw.Draw(img)
    for p in pts[:2] + [(72, 160), (112, 148), (180, 148)]:
        d.line(P([core, p]), fill=(255, 255, 255, 110), width=3 * K)
    tail = mask_poly([(72, 160), (110, 238), (148, 222), (112, 148)])
    img.alpha_composite(solid(tail, "#06102A", 40))
    shine(img, [(34, 46), (34, 150)], 12, 160)
    dot(img, tip, 22)
    return finish(img), tip


def gem(pal):
    A = Axis((26, 26))
    out = A.pts([(0, 0), (150, 62), (205, 46), (230, 0), (205, -46), (150, -62)])
    m = mask_poly(out)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    t = A.pts([(150, 30), (196, 22), (196, -22), (150, -30)])          # mặt bàn
    shades = [
        ([A(0), A(150, 62), A(150, 30)], "#FFFFFF", 70),
        ([A(0), A(150, 30), A(150, -30)], "#FFFFFF", 25),
        ([A(0), A(150, -30), A(150, -62)], "#06102A", 70),
        ([A(150, 62), A(205, 46), A(196, 22), A(150, 30)], "#FFFFFF", 30),
        ([A(150, -62), A(205, -46), A(196, -22), A(150, -30)], "#06102A", 90),
        ([A(205, 46), A(230, 0), A(196, 22)], "#06102A", 30),
        ([A(205, -46), A(230, 0), A(196, -22)], "#06102A", 110),
    ]
    for poly, col, al in shades:
        img.alpha_composite(solid(mask_poly(poly), col, al))
    img.alpha_composite(solid(mask_poly(t), "#FFFFFF", 45))
    d = ImageDraw.Draw(img)
    for a, b in [(A(0), A(150, 30)), (A(0), A(150, -30)), (A(150, 30), A(150, -30)), (A(150, 62), A(150, 30)),
                 (A(150, -62), A(150, -30)), (A(196, 22), A(196, -22)), (A(150, 30), A(196, 22)),
                 (A(150, -30), A(196, -22)), (A(196, 22), A(230, 0)), (A(196, -22), A(230, 0))]:
        d.line(P([a, b]), fill=(255, 255, 255, 120), width=3 * K)
    sp = A(172, 8)
    star4(img, sp, 16, "#FFFFFF", 230)
    dot(img, (26, 26), 22)
    return finish(img), (26, 26)


def star4(img, c, r, color="#FFFFFF", alpha=255, inner=0.22):
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * inner
        pts.append((c[0] + rr * math.cos(ang), c[1] + rr * math.sin(ang)))
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(P(chaikin(pts, 1)), fill=rgb(color) + (alpha,))
    img.alpha_composite(layer)


def flame(pal):
    A = Axis((24, 24))
    right = [(0, 0), (52, 30), (78, 62), (86, 96), (112, 66), (142, 84), (176, 88), (214, 66), (236, 28), (240, 0)]
    left = [(0, 0), (66, -30), (96, -50), (100, -84), (126, -54), (158, -66), (200, -70), (230, -42), (240, 0)]
    poly = right + left[::-1][1:-1]
    sm = chaikin(A.pts(poly), 3)
    m = mask_poly(sm)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    core_c = A(178, 4)
    core = [(core_c[0] + (x - core_c[0]) * 0.52, core_c[1] + (y - core_c[1]) * 0.52) for x, y in sm]
    cm = mask_poly(core)
    img.alpha_composite(solid(cm.filter(ImageFilter.GaussianBlur(6 * K)), "#FFFFFF", 150))
    img.alpha_composite(solid(mask_poly([(core_c[0] + (x - core_c[0]) * 0.3, core_c[1] + (y - core_c[1]) * 0.3)
                                         for x, y in sm]).filter(ImageFilter.GaussianBlur(4 * K)), "#FFFFFF", 200))
    shine(img, A.pts([(26, -8), (90, -26)]), 12, 150)
    dot(img, (24, 24), 22)
    return finish(img), (24, 24)


def spear(pal):
    A = Axis((24, 24))
    leaf = [A(u, v) for u, v in
            [(0, 0), (30, 24), (70, 36), (108, 20), (124, 0), (108, -20), (70, -36), (30, -24)]]
    leaf = chaikin(leaf, 2)
    shaft = A.pts([(116, 11), (282, 11), (282, -11), (116, -11)])
    bind = A.pts([(116, 17), (140, 17), (140, -17), (116, -17)])
    m = mask_poly(leaf)
    ImageDraw.Draw(m).polygon(P(shaft), fill=255)
    ImageDraw.Draw(m).polygon(P(bind), fill=255)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    img.alpha_composite(solid(mask_poly(A.pts([(0, 0), (30, -24), (70, -36), (108, -20), (124, 0)])), "#06102A", 70))
    img.alpha_composite(solid(mask_poly(shaft), "#06102A", 50))
    d = ImageDraw.Draw(img)
    d.line(P(A.pts([(14, 0), (112, 0)])), fill=(255, 255, 255, 140), width=4 * K)
    for u in (124, 132):
        d.line(P(A.pts([(u, 16), (u, -16)])), fill=(11, 13, 18, 140), width=2 * K)
    shine(img, A.pts([(22, 10), (78, 22)]), 10, 150)
    dot(img, (24, 24), 22)
    return finish(img), (24, 24)


def feather(pal):
    A = Axis((24, 24), 47)
    top = [(0, 0), (40, 18), (100, 38), (150, 44), (196, 36), (232, 18), (248, 0)]
    bot = [(0, 0), (50, -14), (110, -30), (160, -34), (206, -26), (240, -10), (248, 0)]
    vane = chaikin(A.pts(top + bot[::-1][1:-1]), 3)
    m = mask_poly(vane)
    d = ImageDraw.Draw(m)
    for u, v, s in [(120, 44, 1), (170, 46, 1), (140, -34, -1), (196, -30, -1)]:      # khe lông
        d.polygon(P([A(u - 6, v * 1.3), A(u + 10, v * 0.25), A(u + 2, v * 1.3)]), fill=0)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    img.alpha_composite(solid(mask_poly(chaikin(A.pts(bot), 2) + [A(248, 0)]), "#06102A", 55))
    det = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    dr = ImageDraw.Draw(det)
    for u in range(50, 236, 22):
        dr.line(P([A(u, 0), A(u + 26, 30)]), fill=(255, 255, 255, 70), width=2 * K)
        dr.line(P([A(u, 0), A(u + 22, -24)]), fill=(6, 16, 42, 70), width=2 * K)
    dr.line(P(A.pts([(6, 0), (246, 0)])), fill=(255, 255, 255, 210), width=5 * K)
    a = det.getchannel("A")
    from PIL import ImageChops
    det.putalpha(ImageChops.multiply(a, m))
    img.alpha_composite(det)
    dot(img, (24, 24), 22)
    return finish(img), (24, 24)


def arrow_shot(pal):
    A = Axis((24, 24))
    head = A.pts([(0, 0), (66, 32), (52, 0), (66, -32)])
    shaft = A.pts([(48, 9), (246, 9), (246, -9), (48, -9)])
    fl1 = chaikin(A.pts([(180, 8), (228, 40), (262, 40), (240, 8)]), 2)
    fl2 = chaikin(A.pts([(180, -8), (228, -40), (262, -40), (240, -8)]), 2)
    m = blank()
    d = ImageDraw.Draw(m)
    for poly in (head, shaft, fl1, fl2):
        d.polygon(P(poly), fill=255)
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    img.alpha_composite(solid(mask_poly(A.pts([(0, 0), (66, -32), (52, 0)])), "#06102A", 80))
    img.alpha_composite(solid(mask_poly(fl2), "#06102A", 60))
    dr = ImageDraw.Draw(img)
    for u in (196, 210, 224):
        dr.line(P([A(u, 8), A(u + 18, 30)]), fill=(255, 255, 255, 90), width=2 * K)
        dr.line(P([A(u, -8), A(u + 18, -30)]), fill=(255, 255, 255, 60), width=2 * K)
    shine(img, A.pts([(14, 6), (40, 16)]), 8, 170)
    dot(img, (24, 24), 20)
    return finish(img), (24, 24)


def neon_arrow(pal):
    pts = [(24, 24), (24, 200), (74, 156), (104, 226), (138, 212), (108, 146), (174, 146)]
    outer = mask_poly(pts)
    inner = blank()
    # khung rỗng: vùng trong co lại 26 px
    m_np = np.array(outer) > 127
    dist = ndimage.distance_transform_edt(m_np)
    ring = Image.fromarray((np.clip(26 * K / 4 + 0.5 - np.abs(dist - 13 * K / 4) * 2, 0, 1) * 255).astype(np.uint8))
    ring = Image.fromarray((np.clip((dist <= 48) & m_np, 0, 1) * 255).astype(np.uint8))
    hollow = Image.fromarray(((dist > 48) * 255).astype(np.uint8))
    img = frame(outer, outline=22, rim=6)
    img.alpha_composite(solid(hollow, "#0B0D12", 70))                   # lòng tối, trong suốt phần lớn
    glow = gradient(ring, pal)
    img.alpha_composite(glow)
    halo = dilate(hollow, 0).filter(ImageFilter.GaussianBlur(10 * K))
    inner_glow = gradient(ImageChopsMul(halo, hollow), pal)
    inner_glow.putalpha(ImageChopsMul(halo, hollow).point(lambda v: int(v * 0.75)))
    img.alpha_composite(inner_glow)
    dot(img, (24, 24), 20)
    return finish(img), (24, 24)


def ImageChopsMul(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def crosshair(pal):
    c = (128, 128)
    m = blank()
    d = ImageDraw.Draw(m)
    R, w = 86, 16
    d.ellipse(P([(c[0] - R, c[1] - R), (c[0] + R, c[1] + R)]), outline=255, width=w * K)
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        p1 = (c[0] + (R - 6) * math.cos(a), c[1] + (R - 6) * math.sin(a))
        p2 = (c[0] + (R - 44) * math.cos(a), c[1] + (R - 44) * math.sin(a))
        d.line(P([p1, p2]), fill=255, width=12 * K)
    for ang in (45, 135, 225, 315):     # khe hở trên vòng
        a = math.radians(ang)
        q = (c[0] + R * math.cos(a), c[1] + R * math.sin(a))
        d.ellipse(P([(q[0] - 9, q[1] - 9), (q[0] + 9, q[1] + 9)]), fill=0)
    img = frame(m, outline=20, rim=6)
    img.alpha_composite(gradient(m, pal))
    hl = blank()
    ImageDraw.Draw(hl).arc(P([(c[0] - R + 3, c[1] - R + 3), (c[0] + R - 3, c[1] + R - 3)]), 200, 250,
                           fill=255, width=4 * K)
    img.alpha_composite(solid(hl, "#FFFFFF", 170))
    dot(img, c, 20)
    return finish(img), c


def rune(pal):
    c = (128, 128)
    m = blank()
    R = 92
    hexa = [(c[0] + R * math.cos(math.radians(60 * i - 90)), c[1] + R * math.sin(math.radians(60 * i - 90)))
            for i in range(6)]
    ImageDraw.Draw(m).polygon(P(chaikin(hexa, 2)), fill=255)
    img = frame(m)
    stone = gradient(m, ["#2A3550", "#161C2C", "#0D111C"])
    img.alpha_composite(stone)
    # đá tối, ký tự phát sáng màu theo bảng màu
    g = blank()
    d = ImageDraw.Draw(g)
    lw = 11 * K
    d.line(P([(128, 62), (128, 196)]), fill=255, width=lw)
    d.line(P([(128, 120), (86, 76)]), fill=255, width=lw)
    d.line(P([(128, 120), (170, 76)]), fill=255, width=lw)
    d.line(P([(96, 196), (160, 196)]), fill=255, width=lw)
    g = g.filter(ImageFilter.GaussianBlur(1))
    glow = gradient(dilate(g, 18).filter(ImageFilter.GaussianBlur(6 * K)), pal)
    glow.putalpha(dilate(g, 18).filter(ImageFilter.GaussianBlur(6 * K)).point(lambda v: int(v * 0.8)))
    img.alpha_composite(glow)
    img.alpha_composite(gradient(g, pal))
    img.alpha_composite(solid(g.filter(ImageFilter.GaussianBlur(2)).point(lambda v: v // 3), "#FFFFFF"))
    rim = blank()
    ImageDraw.Draw(rim).line(P(chaikin(hexa, 2) + [chaikin(hexa, 2)[0]]), fill=255, width=3 * K)
    img.alpha_composite(solid(rim, "#FFFFFF", 50))
    dot(img, c, 16)
    return finish(img), c


def orb(pal):
    c = (128, 128)
    R = 88
    m = blank()
    ImageDraw.Draw(m).ellipse(P([(c[0] - R, c[1] - R), (c[0] + R, c[1] + R)]), fill=255)
    img = frame(m)
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float32)
    dx, dy = xs - (c[0] - 26) * K, ys - (c[1] - 30) * K
    t = np.clip(np.sqrt(dx * dx + dy * dy) / (R * 1.55 * K), 0, 1)[..., None]
    cs = [np.array(rgb(x), np.float32) for x in pal]
    col = np.where(t < 0.5, cs[0] + (cs[1] - cs[0]) * (t / 0.5), cs[1] + (cs[2] - cs[1]) * ((t - 0.5) / 0.5))
    body = Image.fromarray(col.astype(np.uint8), "RGB").convert("RGBA")
    body.putalpha(m)
    img.alpha_composite(body)
    sw = blank()
    d = ImageDraw.Draw(sw)
    for r0, a0, a1 in [(58, 200, 320), (36, 20, 150), (70, 30, 80)]:
        d.arc(P([(c[0] - r0, c[1] - r0), (c[0] + r0, c[1] + r0)]), a0, a1, fill=255, width=6 * K)
    img.alpha_composite(solid(sw.filter(ImageFilter.GaussianBlur(2 * K)), "#FFFFFF", 120))
    hl = blank()
    ImageDraw.Draw(hl).ellipse(P([(c[0] - 58, c[1] - 66), (c[0] - 10, c[1] - 34)]), fill=255)
    img.alpha_composite(solid(hl.filter(ImageFilter.GaussianBlur(5 * K)), "#FFFFFF", 200))
    core = blank()
    ImageDraw.Draw(core).ellipse(P([(c[0] - 18, c[1] - 18), (c[0] + 18, c[1] + 18)]), fill=255)
    img.alpha_composite(solid(core.filter(ImageFilter.GaussianBlur(8 * K)), "#FFFFFF", 220))
    dot(img, c, 14)
    return finish(img), c


def star(pal):
    c = (128, 128)
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rr = 104 if i % 2 == 0 else 30
        pts.append((c[0] + rr * math.cos(ang), c[1] + rr * math.sin(ang)))
    m = mask_poly(chaikin(pts, 1))
    img = frame(m)
    img.alpha_composite(gradient(m, pal))
    for i in range(4):          # mỗi cánh nửa sáng nửa tối
        a = math.pi / 2 * i - math.pi / 2
        tipp = (c[0] + 104 * math.cos(a), c[1] + 104 * math.sin(a))
        side = (c[0] + 30 * math.cos(a + math.pi / 4), c[1] + 30 * math.sin(a + math.pi / 4))
        img.alpha_composite(solid(mask_poly([c, tipp, side]), "#06102A", 70))
    star4(img, (204, 52), 20, "#FFFFFF", 235)
    dot(img, c, 16)
    return finish(img), c


DESIGNS = [
    ("ez_crosshair", "Tâm ngắm Neon", "Neon Crosshair", crosshair),
    ("ez_sword", "Mũi kiếm", "Blade", sword),
    ("ez_crystal", "Mũi tên Pha lê", "Crystal Arrow", crystal_arrow),
    ("ez_gem", "Viên ngọc", "Gem", gem),
    ("ez_rune", "Ký tự Rune", "Rune", rune),
    ("ez_orb", "Cầu năng lượng", "Energy Orb", orb),
    ("ez_flame", "Ngọn lửa", "Flame", flame),
    ("ez_spear", "Mũi giáo", "Spear", spear),
    ("ez_feather", "Lông vũ", "Feather", feather),
    ("ez_star", "Ngôi sao", "Star", star),
    ("ez_shot", "Mũi tên Bắn", "Arrow Shot", arrow_shot),
    ("ez_neon", "Mũi tên Neon", "Neon Arrow", neon_arrow),
]

if __name__ == "__main__":
    import json
    import os
    import sys
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    meta = {}
    for key, vi, en, fn in DESIGNS:
        im, hot = fn(PAL)
        im.save(f"{out}/{key}.png", optimize=True)
        meta[key] = {"vi": vi, "en": en, "hot": hot}
        print(key, hot)
    json.dump(meta, open(f"{out}/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

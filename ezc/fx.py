"""Hiệu ứng: vệt, gợn sóng khi bấm, tìm con trỏ."""

import colorsys
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from .colors import mix
from .icons import STAR_PTS


FX_TRAILS = [("off", "Tắt"), ("sparkle", "Lấp lánh"), ("neon", "Vệt neon"),
             ("rainbow", "Cầu vồng"), ("ghost", "Bóng mờ"), ("bubble", "Bong bóng")]
FX_CLICKS = [("off", "Tắt"), ("ripple", "Gợn sóng"), ("burst", "Pháo hoa")]
EZ_COLORS = ["#2EE59D", "#2F80FF", "#FF2E93"]
FX_DENSITY = {"low": 0.5, "mid": 1.0, "high": 2.0}
FX_BOX = 600          # kích thước tối đa của lớp hiệu ứng quanh con trỏ


def hue_color(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 0.75, 1.0)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def star_sprite(color, size):
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = n / 2
    r = n * 0.36
    d.polygon([(c + x * r, c + y * r) for x, y in STAR_PTS], fill=color)
    d.ellipse([c - r * 0.12, c - r * 0.12, c + r * 0.12, c + r * 0.12], fill="#FFFFFF")
    im = im.resize((size, size), Image.LANCZOS)
    glow = Image.new("RGBA", im.size, color)
    glow.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(size / 7)).point(lambda v: int(v * 0.8)))
    glow.alpha_composite(im)
    return glow


def soft_dot(color, size, hard=0.45):
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = n / 2
    d.ellipse([c - n * 0.22, c - n * 0.22, c + n * 0.22, c + n * 0.22], fill=color)
    im = im.filter(ImageFilter.GaussianBlur(n * 0.08))
    core = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(core).ellipse([c - n * 0.22 * hard, c - n * 0.22 * hard, c + n * 0.22 * hard, c + n * 0.22 * hard],
                                 fill=mix(color, "#FFFFFF", 0.55))
    im.alpha_composite(core.filter(ImageFilter.GaussianBlur(n * 0.03)))
    return im.resize((size, size), Image.LANCZOS)


def bubble_sprite(color, size):
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, n // 12)
    d.ellipse([w, w, n - w, n - w], outline=color, width=w)
    d.ellipse([n * 0.28, n * 0.24, n * 0.42, n * 0.38], fill="#FFFFFF")
    return im.resize((size, size), Image.LANCZOS)


class FxEngine:
    """Hệ hạt cho hiệu ứng vệt chuột và click, vẽ ra một ảnh RGBA quanh con trỏ."""

    def __init__(self):
        self.parts = []      # [x, y, vx, vy, age, life, sprite_key, gravity]
        self.trail = []      # [(x, y, t)]
        self.ghosts = []     # [(x, y, t)]
        self.rings = []      # [x, y, age, color]
        self.cache = {}
        self.last = None
        self.dist = 0.0
        self.hue = 0.0
        self.last_ghost = 0.0
        self.ghost_img = None

    def sprite(self, kind, color, size):
        key = (kind, color, size)
        im = self.cache.get(key)
        if im is None:
            if len(self.cache) > 400:
                self.cache.clear()
            im = {"star": star_sprite, "dot": soft_dot, "bubble": bubble_sprite}[kind](color, size)
            self.cache[key] = im
        return im

    def faded(self, key, im, alpha):
        q = max(0, min(8, round(alpha * 8)))
        if q == 0:
            return None
        if q == 8:
            return im
        k = ("fade", key, q)
        out = self.cache.get(k)
        if out is None:
            out = im.copy()
            out.putalpha(im.getchannel("A").point(lambda v, f=q / 8: int(v * f)))
            self.cache[k] = out
        return out

    def busy(self):
        return bool(self.parts or self.trail or self.ghosts or self.rings)

    def clear(self):
        self.parts.clear(); self.trail.clear(); self.ghosts.clear(); self.rings.clear()
        self.last = None

    def update(self, now, dt, pos, clicked, cfg, palette, ghost_img):
        trail = cfg["fx_trail"]
        dens = FX_DENSITY.get(cfg["fx_density"], 1.0)
        x, y = pos
        moved = 0.0
        if self.last is not None:
            moved = math.hypot(x - self.last[0], y - self.last[1])
        self.last = pos
        if moved > 400:          # nhảy chuột quá xa (đổi màn hình...) -> bỏ qua
            moved = 0
            self.trail.clear()
        self.dist += moved
        self.hue = (self.hue + dt * 0.6) % 1.0

        if trail in ("sparkle", "bubble"):
            step = (14 if trail == "sparkle" else 22) / dens
            while self.dist >= step:
                self.dist -= step
                col = random.choice(palette)
                if trail == "sparkle":
                    size = random.choice((14, 18, 22, 26))
                    self.parts.append([x + random.uniform(-8, 8), y + random.uniform(-8, 8),
                                       random.uniform(-25, 25), random.uniform(5, 40), 0.0,
                                       random.uniform(0.45, 0.8), ("star", col, size), 0.0])
                else:
                    size = random.choice((10, 14, 18))
                    self.parts.append([x + random.uniform(-6, 6), y + random.uniform(-4, 4),
                                       random.uniform(-15, 15), random.uniform(-70, -35), 0.0,
                                       random.uniform(0.7, 1.1), ("bubble", col, size), 0.0])
        else:
            self.dist = 0.0
        if trail in ("neon", "rainbow"):
            if moved > 0.5 or not self.trail:
                self.trail.append((x, y, now))
        if trail == "ghost" and ghost_img is not None:
            self.ghost_img = ghost_img
            if moved > 2 and now - self.last_ghost > 0.03:
                self.ghosts.append((x, y, now))
                self.last_ghost = now
        life_trail = 0.32 * (0.8 + 0.2 * dens)
        self.trail = [p for p in self.trail if now - p[2] < life_trail][-80:]
        self.ghosts = [p for p in self.ghosts if now - p[2] < 0.22][-8:]

        if clicked:
            if cfg["fx_click"] == "ripple":
                self.rings.append([x, y, 0.0, random.choice(palette)])
            elif cfg["fx_click"] == "burst":
                n = int(14 * (0.7 + 0.3 * dens))
                for i in range(n):
                    a = 2 * math.pi * i / n + random.uniform(-0.2, 0.2)
                    sp = random.uniform(140, 300)
                    self.parts.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 0.0,
                                       random.uniform(0.5, 0.8), ("dot", random.choice(palette), 16), 420.0])

        alive = []
        for p in self.parts:
            p[4] += dt
            if p[4] < p[5]:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[3] += p[7] * dt
                alive.append(p)
        self.parts = alive
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.5]

    def render(self, now, cursor, cfg, palette, ghost_hot):
        cx, cy = cursor
        half = FX_BOX // 2
        left, top = int(cx - half), int(cy - half)
        items = []          # (ảnh, x, y)
        for p in self.parts:
            im = self.sprite(*p[6])
            t = p[4] / p[5]
            if p[6][0] == "star":
                a = math.sin(min(1.0, t) * math.pi) ** 0.7
            else:
                a = 1.0 - t
            f = self.faded(p[6], im, a)
            if f is not None:
                items.append((f, p[0] - im.width / 2, p[1] - im.height / 2))
        if self.trail:
            pts = self.trail
            stamps = []
            for i in range(1, len(pts)):
                (x0, y0, _), (x1, y1, t1) = pts[i - 1], pts[i]
                seg = math.hypot(x1 - x0, y1 - y0)
                k = max(1, int(seg / 4))
                for j in range(k):
                    u = j / k
                    stamps.append((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, t1))
            stamps.append((pts[-1][0], pts[-1][1], pts[-1][2]))
            n = len(stamps)
            for i, (sx, sy, st) in enumerate(stamps):
                frac = (i + 1) / n
                size = 8 + 4 * round(frac * 5)                 # 8..28 px, lượng tử hóa để dùng cache
                if cfg["fx_trail"] == "rainbow":
                    col = hue_color(round((self.hue + frac * 0.6) * 24) / 24)
                else:
                    col = palette[min(len(palette) - 1, int(frac * len(palette)))]
                im = self.sprite("dot", col, size)
                f = self.faded(("dot", col, size), im, 0.25 + 0.75 * frac)
                if f is not None:
                    items.append((f, sx - size / 2, sy - size / 2))
        if self.ghosts and self.ghost_img is not None:
            gi = self.ghost_img
            for (gx, gy, gt) in self.ghosts:
                a = 0.45 * (1 - (now - gt) / 0.22)
                f = self.faded(("ghost", id(gi)), gi, a)
                if f is not None:
                    items.append((f, gx - ghost_hot[0], gy - ghost_hot[1]))

        box = Image.new("RGBA", (FX_BOX, FX_BOX), (0, 0, 0, 0))
        drawn = False
        if self.rings:
            d = ImageDraw.Draw(box)
            for x, y, age, col in self.rings:
                t = age / 0.5
                r = 10 + 60 * (1 - (1 - t) ** 3)
                c = mix(col, "#000000", 0)
                rgb = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
                alpha = int(255 * (1 - t))
                bx, by = x - left, y - top
                if r < bx < FX_BOX - r and r < by < FX_BOX - r:
                    d.ellipse([bx - r, by - r, bx + r, by + r], outline=rgb + (alpha,), width=4)
                    r2 = r * 0.6
                    d.ellipse([bx - r2, by - r2, bx + r2, by + r2], outline=(255, 255, 255, alpha // 2), width=2)
                    drawn = True
        for im, x, y in items:
            ix, iy = int(x - left), int(y - top)
            if 0 <= ix and 0 <= iy and ix + im.width <= FX_BOX and iy + im.height <= FX_BOX:
                box.alpha_composite(im, (ix, iy))
                drawn = True
        if not drawn:
            return None, (left, top)
        bb = box.getbbox()
        if bb is None:
            return None, (left, top)
        return box.crop(bb), (left + bb[0], top + bb[1])


def fx_icon(kind, size=48):
    """Ảnh minh họa nhỏ cho các ô chọn hiệu ứng."""
    S = 4
    n = size * S
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    G_, B_, P_ = EZ_COLORS
    if kind == "aura":
        base = [(0, 0), (0, 0.5), (0.13, 0.38), (0.22, 0.58), (0.3, 0.54), (0.21, 0.35), (0.38, 0.35)]
        d.polygon([(n * (0.2 + x), n * (0.28 + y)) for x, y in base], fill=P_)
        for (cx, cy, r, col) in ((0.7, 0.24, 0.13, "#FFFFFF"), (0.8, 0.52, 0.08, G_), (0.18, 0.84, 0.07, B_)):
            d.polygon([(n * cx + x * n * r, n * cy + y * n * r) for x, y in STAR_PTS], fill=col)
    elif kind == "off":
        w = int(3 * S)
        d.ellipse([n * 0.22, n * 0.22, n * 0.78, n * 0.78], outline="#8B93A7", width=w)
        d.line([(n * 0.32, n * 0.68), (n * 0.68, n * 0.32)], fill="#8B93A7", width=w)
    elif kind == "sparkle":
        for (cx, cy, r, col) in ((0.32, 0.36, 0.2, "#FFFFFF"), (0.66, 0.6, 0.15, P_), (0.66, 0.24, 0.09, G_), (0.3, 0.74, 0.08, B_)):
            d.polygon([(n * cx + x * n * r, n * cy + y * n * r) for x, y in STAR_PTS], fill=col)
    elif kind in ("neon", "rainbow"):
        pts = [(0.15 + 0.7 * i / 30, 0.62 - 0.28 * math.sin(i / 30 * math.pi * 1.4)) for i in range(31)]
        for i, (x, y) in enumerate(pts):
            f = i / 30
            col = hue_color(f * 0.8) if kind == "rainbow" else [G_, B_, P_][min(2, int(f * 3))]
            r = n * (0.02 + 0.05 * f)
            d.ellipse([n * x - r, n * y - r, n * x + r, n * y + r], fill=col)
    elif kind == "ghost":
        base = [(0, 0), (0, 0.5), (0.13, 0.38), (0.22, 0.58), (0.3, 0.54), (0.21, 0.35), (0.38, 0.35)]
        for k, (ox, a) in enumerate(((0.1, 70), (0.25, 140), (0.42, 255))):
            col = tuple(int(P_[i:i + 2], 16) for i in (1, 3, 5)) + (a,)
            d.polygon([(n * (ox + x), n * (0.22 + y)) for x, y in base], fill=col)
    elif kind == "bubble":
        for (cx, cy, r, col) in ((0.36, 0.62, 0.17, B_), (0.64, 0.38, 0.12, P_), (0.4, 0.26, 0.07, G_)):
            d.ellipse([n * (cx - r), n * (cy - r), n * (cx + r), n * (cy + r)], outline=col, width=int(2.5 * S))
    elif kind == "ripple":
        for r, col in ((0.12, "#FFFFFF"), (0.24, B_), (0.36, P_)):
            d.ellipse([n * (0.5 - r), n * (0.5 - r), n * (0.5 + r), n * (0.5 + r)], outline=col, width=int(2.5 * S))
    elif kind == "burst":
        for i in range(10):
            a = 2 * math.pi * i / 10
            col = EZ_COLORS[i % 3]
            x0, y0 = n * (0.5 + math.cos(a) * 0.12), n * (0.5 + math.sin(a) * 0.12)
            x1, y1 = n * (0.5 + math.cos(a) * 0.36), n * (0.5 + math.sin(a) * 0.36)
            d.line([(x0, y0), (x1, y1)], fill=col, width=int(3 * S))
    return im.resize((size, size), Image.LANCZOS)

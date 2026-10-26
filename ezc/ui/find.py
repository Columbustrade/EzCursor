"""Tìm con trỏ nhanh (phím tắt hoặc lắc chuột)."""

import ctypes
import math
import time
from ctypes import wintypes

from PIL import Image, ImageDraw

from ..winapi import user32
from ..colors import _rgb


class FindMixin:
    FIND_TIME = 0.9

    def start_find(self):
        """Phóng to con trỏ + tỏa vòng sáng ~1 giây để tìm thấy con trỏ ngay."""
        if not self.enabled:
            return
        self.find_t0 = time.perf_counter()
        self.find_ring_only = not self.active or self.system_mode()
        self.find_cool = self.find_t0 + 1.5

    def find_frame(self, now):
        p = (now - self.find_t0) / self.FIND_TIME
        if p >= 1:
            self.end_find()
            return
        base = None if self.find_ring_only else self.shown_img
        hot = self.ov_hot
        size = self.eff_size()
        bw = max(base.size) if base is not None else size
        bump = math.sin(math.pi * min(1.0, p / 0.9)) ** 0.7
        k = 1 + 1.5 * bump
        C = int(bw * 3.6) + 8
        C -= C % 2
        cv = Image.new("RGBA", (C, C), (0, 0, 0, 0))
        d = ImageDraw.Draw(cv)
        col = _rgb(self.glow_color())
        lw = max(4, size // 10)
        for delay in (0.0, 0.28):
            q = (p - delay) / (1 - delay)
            if 0 <= q <= 1:
                r = size * 0.45 + q * (C / 2 - lw - size * 0.45)
                a = int(255 * (1 - q) ** 1.3)
                d.ellipse([C / 2 - r, C / 2 - r, C / 2 + r, C / 2 + r], outline=col + (a,), width=lw)
                d.ellipse([C / 2 - r - lw, C / 2 - r - lw, C / 2 + r + lw, C / 2 + r + lw],
                          outline=(255, 255, 255, a // 3), width=max(1, lw // 2))
        if base is not None:
            sw, sh = max(1, round(base.width * k)), max(1, round(base.height * k))
            big = base.resize((sw, sh), Image.BILINEAR)
            ox, oy = round(C / 2 - hot[0] * k), round(C / 2 - hot[1] * k)
            cv.alpha_composite(big, (max(0, ox), max(0, oy)),
                               (max(0, -ox), max(0, -oy)))
        self.ovl.set_image(cv)
        self.find_hot = (C // 2, C // 2)
        if not self.ovl.visible:
            self.ovl.show(True)
        self.move_overlay()

    def end_find(self):
        self.find_t0 = None
        self.find_hot = None
        if self.shown_img is not None:
            self.ovl.set_image(self.shown_img)
        if self.find_ring_only and (not self.active or self.system_mode()):
            self.ovl.show(False)
        self.find_ring_only = False
        self.move_overlay()

    def check_shake(self, now):
        """Lắc chuột qua lại nhanh (≥4 lần đổi hướng trong 0,8 giây) thì tìm con trỏ."""
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if self.sh_last_x is None:
            self.sh_last_x = pt.x
            return
        dx = pt.x - self.sh_last_x
        self.sh_last_x = pt.x
        if dx:
            sign = 1 if dx > 0 else -1
            if sign == self.sh_dir:
                self.sh_seg += abs(dx)
            else:
                if self.sh_seg >= 60 * self.cur_scale:
                    self.sh_rev.append(now)
                self.sh_dir, self.sh_seg = sign, abs(dx)
        self.sh_rev = [t for t in self.sh_rev if now - t < 0.8]
        if len(self.sh_rev) >= 4 and now > self.find_cool and self.find_t0 is None:
            self.sh_rev = []
            self.start_find()

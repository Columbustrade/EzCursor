"""Dựng ảnh con trỏ và các khung hình (dựng từng phần để không làm khựng con trỏ)."""

import collections.abc
import json
import math
import time

from PIL import Image, ImageTk

from ..config import OMBRE_SPEEDS, STYLE_KEYS
from ..colors import luminance, tint_image
from ..ombre import OMBRE_FRAMES, apply_ombre, ombre_lut, ombre_tmap
from ..theme import ACCENT
from ..bibata import (
    BIBATA_DIR, BIBATA_META, OWN_BY_ID, bibata_colors, bibata_image, own_image, own_image_colored)
from ..shapes import render_shape
from ..overlay import add_glow, add_outline, outline_width, pad_image


class RenderMixin:
    def preview_color(self):
        if self.cfg["shape"] == "Ảnh tải lên" and self.src_img is not None and not self.cfg["tint_image"]:
            return ACCENT
        return self.cfg["color"]

    def glow_color(self):
        return self.composed[2] if self.composed else self.preview_color()

    def compose_cursor(self, outline=None, phase=0.0):
        """Ảnh con trỏ hoàn chỉnh dùng cho cả overlay lẫn xem trước: (ảnh, điểm click, màu quầng).
        outline: màu viền khi giữ chuột (None = không viền). phase: vị trí dải màu khi ombre chuyển động."""
        c = self.cfg
        s = self.eff_size()
        ombre = c["ombre"]
        oc = c["ombre_colors"]
        if own_image(c["shape"]) is not None:
            _, _, _, (hx, hy), glow_col = OWN_BY_ID[c["shape"]]
            if ombre:
                im = own_image(c["shape"]).resize((s, s), Image.LANCZOS)
            elif c["own_theme"] == "custom":
                im = own_image_colored(c["shape"], c["color"]).resize((s, s), Image.LANCZOS)
                glow_col = c["color"]
            else:
                im = own_image(c["shape"]).resize((s, s), Image.LANCZOS)
            hot = (round(hx * s / 256), round(hy * s / 256))
        elif c["shape"] == "Bibata" and BIBATA_DIR.exists():
            variant = self.bibata_variant()
            cols = bibata_colors("custom" if ombre else c["bibata_theme"], oc[0] if ombre else c["color"])
            im = bibata_image(BIBATA_DIR, variant, c["bibata_cursor"], cols).resize((s, s), Image.LANCZOS)
            hx, hy = BIBATA_META["hotspots"].get(f"{variant}/{c['bibata_cursor']}", [128, 128])
            hot = (round(hx * s / 256), round(hy * s / 256))
            glow_col = cols[0] if luminance(cols[0]) > 60 else cols[1]
        else:
            shape = c["shape"] if c["shape"] not in ("Bibata",) + tuple(OWN_BY_ID) else "Vòng tròn"
            src = self.src_img
            if src is not None and c["tint_image"] and not ombre:
                src = tint_image(src, c["color"])
            glow_col = oc[0] if ombre else self.preview_color()
            im, hot = render_shape(shape, glow_col, s, src, c["hotspot"], self.src_hot)
        if ombre:
            anim = c["ombre_anim"] and not self.animated_image()
            im = apply_ombre(im, ombre_tmap(im, hot), ombre_lut(oc, phase, anim))
            glow_col = oc[0]
        if c["hold_left"] or c["hold_right"]:      # mọi biến thể cùng kích thước để điểm click không lệch
            w = outline_width(s)
            im, hot = add_outline(im, hot, outline, w) if outline else pad_image(im, hot, w + 2)
        if c["glow"]:
            im, hot = add_glow(im, hot, glow_col)
        return im, hot, glow_col

    def eff_size(self):
        """Kích thước con trỏ thực tế (nhân tỉ lệ màn hình nếu bật)."""
        s = self.cfg["size"]
        return max(16, round(s * self.cur_scale)) if self.cfg["dpi_scale"] else s

    def animated_image(self):
        return (self.cfg["shape"] == "Ảnh tải lên" and self.src_frames is not None
                and len(self.src_frames) > 1 and bool(self.src_steps))

    def bibata_variant(self):
        return self.cfg["bibata_style"] + ("-right" if self.cfg["bibata_hand"] == "left" else "")

    def hold_colors(self):
        c = self.cfg
        out = {None: None}
        if c["hold_left"]:
            out["left"] = c["hold_left_color"]
        if c["hold_right"]:
            out["right"] = c["hold_right_color"]
        return out

    def render_key(self):
        c = self.cfg
        style = json.dumps({k: c[k] for k in STYLE_KEYS}, sort_keys=True, default=str)
        return (style, self.eff_size(), id(self.src_img), self.animated_image())

    def rebuild_overlay(self):
        cache = self.__dict__.setdefault("render_cache", collections.OrderedDict())
        key = self.render_key()
        self.render_key_now = key
        hit = cache.get(key)
        if hit is not None:
            cache.move_to_end(key)
            self.composed, self.variants = hit["composed"], hit["variants"]
        else:
            self.composed = self.compose_cursor()
            self.variants = {k: (self.composed if col is None else self.compose_cursor(col))
                             for k, col in self.hold_colors().items()}
            hit = cache[key] = {"composed": self.composed, "variants": self.variants}
            while len(cache) > 6:
                cache.popitem(last=False)
        # Chỉ giữ khung hình động (nặng RAM) của 2 kiểu dùng gần nhất, vd game đang chơi và desktop.
        # Kiểu cũ hơn chỉ giữ ảnh tĩnh; khi quay lại, khung hình được dựng lại từng phần nên không khựng.
        for old in list(cache.values())[:-2]:
            for k in ("frame_sets", "durations", "photos", "ov_hot"):
                old.pop(k, None)
        im, self.ov_hot, _ = self.composed
        if getattr(self, "sys_cache", None) is not None:
            self.drop_system_cache()
            if self.active and self.system_mode():
                self.apply_system_cursor(force=True)
        self.cursor_frames = None
        self.frame_sets = None
        self.cursor_durations = None
        self.preview_photos = None
        self.show_img(self.variants.get(self.hold_state, self.composed)[0])
        if getattr(self, "_cf_job", None):
            self.ov.after_cancel(self._cf_job)
            self._cf_job = None
        self._builder = None
        if hit.get("frame_sets"):            # khung hình đã dựng trước đó: dùng lại ngay
            self.frame_sets = hit["frame_sets"]
            self.cursor_durations = hit["durations"]
            self.preview_photos = hit["photos"]
            self.ov_hot = hit["ov_hot"]
            self.cursor_frames = self.frame_sets.get(self.hold_state) or self.frame_sets[None]
            self.cf_idx, self.cf_next, self.pv_idx, self.pv_next = 0, 0.0, 0, 0.0
            self.show_img(self.cursor_frames[0])
            if self.active:
                self.move_overlay()
            return
        if self.animated_image():
            self._cf_job = self.ov.after(160, self.build_image_frames)
        elif self.cfg["cursor_sparkle"] or self.ombre_moving():
            self._cf_job = self.ov.after(160, self.build_cursor_frames)

    def remember_frames(self):
        hit = getattr(self, "render_cache", {}).get(getattr(self, "render_key_now", None))
        if hit is not None and self.frame_sets:
            hit.update(frame_sets=self.frame_sets, durations=self.cursor_durations,
                       photos=self.preview_photos, ov_hot=self.ov_hot)

    def ombre_moving(self):
        return self.cfg["ombre"] and self.cfg["ombre_anim"] and not self.animated_image()

    def run_builder(self, gen):
        """Chạy việc dựng khung hình theo từng lượt ngắn, xen giữa là vòng bám chuột."""
        self._builder = gen
        self.step_builder()

    def step_builder(self):
        self._cf_job = None
        gen = getattr(self, "_builder", None)
        if gen is None:
            return
        t0 = time.perf_counter()
        try:
            while time.perf_counter() - t0 < 0.006:
                next(gen)
        except StopIteration:
            self._builder = None
            return
        except Exception:
            self._builder = None
            self.report_error("build frames", once=True)
            return
        self._cf_job = self.ov.after(1, self.step_builder)

    def build_image_frames(self):
        self._cf_job = None
        self.run_builder(self.gen_image_frames())

    def build_cursor_frames(self):
        self._cf_job = None
        self.run_builder(self.gen_cursor_frames())

    def gen_image_frames(self):
        """Khung hình cho ảnh động (.ani / .gif), mỗi khung giữ đúng thời gian của file gốc."""
        if not self.animated_image():
            return
        keep = self.src_img
        src_frames, steps = self.src_frames, self.src_steps
        sets, durs = {}, [ms for _, ms in steps]
        for key, col in self.hold_colors().items():
            cache, frames = {}, []
            for idx, _ms in steps:
                if idx not in cache:
                    self.src_img = src_frames[idx]
                    try:
                        cache[idx] = self.compose_cursor(col)[0]
                    finally:
                        self.src_img = keep
                    yield
                frames.append(cache[idx])
            sets[key] = frames
        frames = sets.get(None)
        if not frames or len({f.size for fs in sets.values() for f in fs}) != 1:
            return
        self.frame_sets = sets
        self.cursor_frames, self.cursor_durations = sets.get(self.hold_state, frames), durs
        self.cf_idx, self.cf_next = 0, 0.0
        self.show_img(self.cursor_frames[0])
        if self.active:
            self.move_overlay()
        self.pv_idx, self.pv_next = 0, 0.0
        photos = {}
        self.preview_photos = [photos.setdefault(id(fr), ImageTk.PhotoImage(fr, master=self.ov)) for fr in frames]
        self.remember_frames()

    def gen_cursor_frames(self):
        """24 khung hình: ngôi sao nhấp nháy quanh con trỏ và/hoặc dải màu ombre chạy (dựng từng khung)."""
        if not self.composed:
            return
        sets, pad = {}, 0
        moving = self.ombre_moving()
        cols = self.hold_colors()
        for key, comp in list(self.variants.items()):
            ims = None
            if moving:
                ims = [comp[0]]
                for i in range(1, OMBRE_FRAMES):
                    ims.append(self.compose_cursor(cols.get(key), i / OMBRE_FRAMES)[0])
                    yield
            if self.cfg["cursor_sparkle"]:
                ctx = self.sparkle_setup(comp)
                pad = ctx["pad"]
                frames = []
                for i in range(24):
                    frames.append(self.sparkle_frame(ctx, i, ims[i] if ims else comp[0]))
                    yield
                sets[key] = frames
            else:
                sets[key] = ims
        hot = self.composed[1]
        self.frame_sets = sets
        self.cursor_frames = sets.get(self.hold_state, sets[None])
        ms = OMBRE_SPEEDS[self.cfg["ombre_speed"]] if moving else 96
        self.cursor_durations = [ms] * len(self.cursor_frames)
        self.cf_idx, self.cf_next = 0, 0.0
        self.pv_idx, self.pv_next = 0, 0.0
        self.ov_hot = (hot[0] + pad, hot[1] + pad)
        self.show_img(self.cursor_frames[0])
        if self.active:
            self.move_overlay()
        self.preview_photos = [ImageTk.PhotoImage(fr, master=self.ov) for fr in sets[None]]
        self.remember_frames()

    def sparkle_setup(self, composed):
        im, hot, gcol = composed
        s = self.eff_size()
        bb = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, im.width, im.height)
        pad = max(8, s // 4)
        W, H = im.width + 2 * pad, im.height + 2 * pad
        x0, y0, x1, y1 = (v + pad for v in bb)
        bw, bh = x1 - x0, y1 - y0
        spots = [  # (x, y, bán kính, màu, thời điểm sáng nhất)
            (x1 - 0.02 * bw, y0 + 0.10 * bh, s * 0.12, "#FFFFFF", 0.15),
            (x1 + 0.06 * bw, y0 + 0.42 * bh, s * 0.075, "#2EE59D", 0.48),
            (x0 + 0.02 * bw, y1 - 0.02 * bh, s * 0.065, gcol, 0.78),
        ]
        return {"W": W, "H": H, "pad": pad, "spots": spots}

    def sparkle_frame(self, ctx, i, base):
        W, H, pad, spots = ctx["W"], ctx["H"], ctx["pad"], ctx["spots"]
        if True:
            t = i / 24
            fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fr.alpha_composite(base, (pad, pad))
            for x, y, R, col, ctr in spots:
                d = min(abs(t - ctr), 1 - abs(t - ctr))
                p = max(0.0, math.cos(min(1.0, d / 0.2) * math.pi / 2)) ** 1.5
                if p < 0.04:
                    continue
                size = max(8, int(R * (0.45 + 0.7 * p) / 0.36))
                st = self.fx.sprite("star", col, size)
                st = self.fx.faded(("star", col, size), st, min(1.0, p * 1.3))
                if st is None:
                    continue
                px, py = int(x - st.width / 2), int(y - st.height / 2)
                if 0 <= px and 0 <= py and px + st.width <= W and py + st.height <= H:
                    fr.alpha_composite(st, (px, py))
            return fr

    def set_hold(self, state):
        """Đổi ảnh con trỏ khi bắt đầu / thôi giữ chuột (ảnh đã vẽ sẵn nên rất nhẹ)."""
        if state == self.hold_state:
            return
        self.hold_state = state
        key = state if state in self.variants else None
        if self.active and self.system_mode():
            self.apply_system_cursor()
            return
        if self.frame_sets:
            self.cursor_frames = self.frame_sets.get(key) or self.frame_sets[None]
            self.show_img(self.cursor_frames[self.cf_idx % len(self.cursor_frames)])
        elif self.variants:
            self.show_img(self.variants.get(key, self.composed)[0])

    def refresh(self):
        self.rebuild_overlay()
        self.update_controls()
        self.update_library()
        self.update_fx_ui()
        self.update_preview()
        self.update_status()
        self.save()

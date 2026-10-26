"""Đọc file con trỏ .cur / .ani và ảnh động."""

import io
import struct
from pathlib import Path

from PIL import Image, ImageSequence


def _ico_entries(data):
    reserved, typ, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or typ not in (1, 2) or not 0 < count < 256:
        raise ValueError("Không phải file .cur/.ico hợp lệ")
    out = []
    for i in range(count):
        w, h, _c, _r, hx, hy, size, off = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        out.append((w or 256, h or 256, hx, hy, size, off, typ))
    return out


def decode_cur(data):
    """Ảnh lớn nhất trong file .cur/.ico và điểm click (None nếu là .ico)."""
    w, h, hx, hy, size, off, typ = max(_ico_entries(data), key=lambda e: e[0] * e[1])
    blob = data[off:off + size]
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        im = Image.open(io.BytesIO(blob)).convert("RGBA")
    else:   # ảnh DIB: gói lại thành file .ico một ảnh để Pillow đọc được
        head = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, size, 22)
        im = Image.open(io.BytesIO(head + blob)).convert("RGBA")
    if typ != 2:
        return im, None
    return im, (round(hx * im.width / w), round(hy * im.height / h))


def decode_ani(data):
    """Con trỏ động .ani: (danh sách ảnh, điểm click, [(chỉ số ảnh, thời gian ms), ...])."""
    if data[:4] != b"RIFF" or data[8:12] != b"ACON":
        raise ValueError("Không phải file .ani hợp lệ")

    def chunks(start, end):
        while start + 8 <= end:
            cid = data[start:start + 4]
            ln = struct.unpack_from("<I", data, start + 4)[0]
            yield cid, start + 8, ln
            start += 8 + ln + (ln & 1)

    frames, rate, seq, jif = [], None, None, 6
    for cid, pos, ln in chunks(12, len(data)):
        if cid == b"anih" and ln >= 36:
            jif = struct.unpack_from("<9I", data, pos)[7] or 6
        elif cid == b"rate":
            rate = list(struct.unpack_from(f"<{ln // 4}I", data, pos))
        elif cid == b"seq ":
            seq = list(struct.unpack_from(f"<{ln // 4}I", data, pos))
        elif cid == b"LIST" and data[pos:pos + 4] == b"fram":
            for c2, p2, l2 in chunks(pos + 4, pos + ln):
                if c2 == b"icon":
                    frames.append(decode_cur(data[p2:p2 + l2]))
    if not frames:
        raise ValueError("File .ani không có ảnh nào")
    order = [i for i in (seq or range(len(frames))) if i < len(frames)] or [0]
    steps = [(fi, max(16, round((rate[i] if rate and i < len(rate) else jif) * 1000 / 60)))
             for i, fi in enumerate(order)]
    return [f[0] for f in frames], frames[0][1], steps


def load_cursor_file(path):
    """Đọc ảnh hoặc file con trỏ: (danh sách ảnh RGBA, điểm click trong ảnh hoặc None, bước hoạt ảnh hoặc None)."""
    ext = Path(path).suffix.lower()
    data = Path(path).read_bytes()
    if ext == ".ani":
        return decode_ani(data)
    if ext == ".cur":
        im, hot = decode_cur(data)
        return [im], hot, None
    im = Image.open(io.BytesIO(data))
    if getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1:
        frames, steps = [], []
        for i, fr in enumerate(ImageSequence.Iterator(im)):
            frames.append(fr.convert("RGBA"))
            steps.append((i, max(20, int(fr.info.get("duration", 100) or 100))))
            if i >= 119:           # tối đa 120 khung hình
                break
        return frames, None, steps
    return [im.convert("RGBA")], None, None

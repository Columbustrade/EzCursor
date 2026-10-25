"""Dựng kho con trỏ trực tuyến cho website EzCursor.

Cách dùng:
    python tools/build_catalog.py <thư mục nguồn> <thư mục catalog của website>

Thư mục nguồn chứa ảnh PNG (khuyên dùng 256 x 256, nền trong suốt) và file catalog-src.json:
    {"cursors": [{"id": "gold_sword", "src": "gold_sword.png", "hot": [26, 26],
                  "name": {"vi": "Kiếm Hoàng kim", "en": "Golden Blade"}, "added": "2026-10-25"}]}
"hot" là điểm click tính theo pixel của ảnh nguồn. Có thể dùng sẵn file .cur / .ani thay cho PNG
(khi đó bỏ "hot", điểm click lấy từ file).

Kết quả trong thư mục catalog: <id>.cur (hoặc .ani), ảnh nhỏ <id>.png và catalog.json mà app đọc.
Thêm con trỏ mới: chép ảnh vào thư mục nguồn, thêm một dòng vào catalog-src.json, chạy lại script,
rồi Commit + Push repo website. App sẽ thấy con trỏ mới ở Bộ sưu tập > Trực tuyến.
"""
import datetime
import hashlib
import io
import json
import re
import shutil
import struct
import sys
from pathlib import Path

from PIL import Image

THUMB = 112


def png_to_cur(im, hot):
    """File .cur một ảnh, dữ liệu ảnh là PNG (Windows Vista trở lên đọc được)."""
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    w, h = im.size
    head = struct.pack("<HHH", 0, 2, 1)
    entry = struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hot[0], hot[1], len(png), 6 + 16)
    return head + entry + png


def main(src_dir, out_dir):
    src_dir, out_dir = Path(src_dir), Path(out_dir)
    spec = json.loads((src_dir / "catalog-src.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for c in spec["cursors"]:
        cid = c["id"]
        assert re.fullmatch(r"[a-z0-9_-]{1,40}", cid), f"id không hợp lệ: {cid}"
        src = src_dir / c["src"]
        ext = src.suffix.lower()
        if ext == ".png":
            im = Image.open(src).convert("RGBA")
            if max(im.size) > 256:
                im.thumbnail((256, 256), Image.LANCZOS)
            data = png_to_cur(im, c["hot"])
            out_name = f"{cid}.cur"
            preview = im
        elif ext in (".cur", ".ani"):
            data = src.read_bytes()
            out_name = f"{cid}{ext}"
            preview = Image.open(c["preview"]).convert("RGBA") if c.get("preview") else None
            if preview is None:
                raise SystemExit(f"{cid}: file {ext} cần thêm \"preview\" (ảnh PNG) để làm ảnh nhỏ")
        else:
            raise SystemExit(f"{cid}: chỉ nhận .png, .cur, .ani")
        (out_dir / out_name).write_bytes(data)
        th = preview.copy()
        th.thumbnail((THUMB, THUMB), Image.LANCZOS)
        pic = Image.new("RGBA", (THUMB, THUMB), (0, 0, 0, 0))
        pic.alpha_composite(th, ((THUMB - th.width) // 2, (THUMB - th.height) // 2))
        pic.save(out_dir / f"{cid}.png", optimize=True)
        items.append({
            "id": cid,
            "name": c["name"],
            "file": out_name,
            "thumb": f"{cid}.png",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "added": c.get("added", datetime.date.today().isoformat()),
            "author": c.get("author", "EzCursor"),
        })
    items.sort(key=lambda x: x["added"], reverse=True)
    cat = {"schema": 1, "updated": datetime.date.today().isoformat(), "cursors": items}
    (out_dir / "catalog.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Đã dựng {len(items)} con trỏ vào {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

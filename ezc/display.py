"""Màn hình: tỉ lệ DPI, phát hiện game Fullscreen."""

import ctypes
import hashlib
import json
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageDraw

from .base import APP_NAME, APP_VERSION, GITHUB_REPO, UPDATE_API, res_path
from .winapi import user32


user32.MonitorFromPoint.restype = wintypes.HANDLE
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]


def monitor_scale(x, y):
    """Tỉ lệ phóng (DPI / 96) của màn hình chứa điểm (x, y)."""
    try:
        mon = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)       # MONITOR_DEFAULTTONEAREST
        dx, dy = wintypes.UINT(), wintypes.UINT()
        if ctypes.windll.shcore.GetDpiForMonitor(mon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0 and dx.value:
            return max(1.0, min(4.0, dx.value / 96))
    except Exception:
        pass
    return 1.0


def fullscreen_exclusive():
    """True khi có ứng dụng Direct3D đang chạy ở chế độ Fullscreen độc quyền."""
    st = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(st)) == 0:
            return st.value == 3             # QUNS_RUNNING_D3D_FULL_SCREEN
    except Exception:
        pass
    return False


def parse_version(v):
    parts = []
    for p in v.strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple((parts + [0, 0, 0])[:3])


def update_configured():
    return not GITHUB_REPO.upper().startswith("TEN-TAI-KHOAN")


def fetch_latest_release():
    req = urllib.request.Request(UPDATE_API, headers={
        "User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), None)
    return {
        "version": data.get("tag_name", "").lstrip("vV"),
        "notes": data.get("body") or "",
        "url": asset["browser_download_url"] if asset else "",
        "size": asset.get("size", 0) if asset else 0,
        # GitHub ghi sẵn mã SHA-256 của file ("sha256:..."); có thì dùng để kiểm tra bản tải về
        "sha256": (asset.get("digest") or "")[7:].lower() if asset and str(asset.get("digest", "")).startswith("sha256:") else "",
        "page": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
    }


def verify_download(path, size, sha256=""):
    """Bộ cài tải về phải đủ dung lượng và đúng mã SHA-256 (nếu GitHub có cung cấp) thì mới được chạy."""
    data_size = Path(path).stat().st_size
    if not data_size or (size and data_size != size):
        return False
    if sha256:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest() == sha256
    return True


def make_tray_icon():
    try:
        return Image.open(res_path("logo.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
    except Exception:
        pass
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(4, 3), (61, 32), (61, 61), (32, 61)]
    d.polygon(pts, fill=(255, 20, 150, 255))
    d.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=5, joint="curve")
    return im

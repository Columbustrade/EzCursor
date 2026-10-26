"""Tên, phiên bản, thư mục dữ liệu, nhật ký và đường dẫn tài nguyên."""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


APP_NAME = "EzCursor"
APP_VERSION = "2.2.2"

# ======== SỬA DÒNG NÀY thành repository GitHub của bạn (tên-tài-khoản/tên-repo) ========
GITHUB_REPO = "ezcursor/EzCursor"
# =========================================================================================
UPDATE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
log = logging.getLogger("ezcursor")

# thư mục gốc của ứng dụng (chứa ezcursor.py, assets/, bibata/, fonts/...)
APP_ROOT = Path(__file__).resolve().parent.parent
ENTRY_SCRIPT = APP_ROOT / "ezcursor.py"


APPDATA = Path(os.environ.get("APPDATA", str(Path.home())))
APP_DIR = APPDATA / APP_NAME
OLD_DIR = APPDATA / "ConTroMau"          # thư mục của bản cũ
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APP_DIR / "config.json"
SHOW_FLAG = APP_DIR / "show.flag"
QUIT_FLAG = APP_DIR / "quit.flag"
SYS_FLAG = APP_DIR / "syscursor.flag"     # có file này = con trỏ Windows đang bị EzCursor thay
MY_DIR = APP_DIR / "my_cursors"        # "Con trỏ của bạn" (1.9.0)
MY_EXTS = {".png", ".gif", ".webp", ".ico", ".cur", ".ani", ".bmp", ".jpg", ".jpeg"}   # bộ cài dùng để yêu cầu thoát


def res_path(*parts):
    """Đường dẫn tới file đi kèm (chạy thường hoặc trong exe PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", APP_ROOT))
    return base.joinpath(*parts)

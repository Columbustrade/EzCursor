"""Tạo file thông tin phiên bản cho PyInstaller (--version-file) từ APP_VERSION trong ezc/base.py.

Cách dùng (build_installer.bat gọi tự động): py tools\\version_info.py build\\version_info.txt
EzCursor.exe khi đó có phiên bản, tên sản phẩm trong Properties / Task Manager."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'EzCursor'),
      StringStruct('FileDescription', 'EzCursor - high-visibility game cursor'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'EzCursor'),
      StringStruct('LegalCopyright', 'GPL-3.0'),
      StringStruct('OriginalFilename', 'EzCursor.exe'),
      StringStruct('ProductName', 'EzCursor'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def app_version():
    """APP_VERSION đọc thẳng từ ezc/base.py (không import: import sẽ tạo thư mục %APPDATA%\\EzCursor)."""
    text = (ROOT / "ezc" / "base.py").read_text(encoding="utf-8")
    return re.search(r'^APP_VERSION = "([0-9.]+)"', text, re.M).group(1)


def version_info_text(version):
    parts = [int(p) for p in version.split(".")][:4]
    nums = tuple(parts + [0] * (4 - len(parts)))
    return TEMPLATE.format(nums=nums, ver=version)


def main(argv):
    out = Path(argv[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(version_info_text(app_version()), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])

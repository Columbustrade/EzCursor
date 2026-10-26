"""Nạp EzCursor với Windows giả lập và cung cấp `ez`: đọc / thay một tên trong mọi module của gói ezc.

    from harness import ez
    ez.key_down = lambda vk: False      # thay ở mọi module đang dùng key_down
    app = ez.App(start_in_tray=True)
"""
import importlib
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

import stubs  # noqa: E402,F401  (phải nạp trước ezc)
import ezc  # noqa: E402
import ezc.app  # noqa: E402

MODULES = [ezc.app]
for pkg in (ezc, importlib.import_module("ezc.ui")):
    for info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        m = importlib.import_module(info.name)
        if m not in MODULES:
            MODULES.append(m)


class _Ez:
    def __getattr__(self, name):
        for m in MODULES:
            if name in vars(m):
                return vars(m)[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        hit = [m for m in MODULES if name in vars(m)]
        if not hit:
            raise AttributeError(f"không module nào có {name}")
        for m in hit:
            setattr(m, name, value)


ez = _Ez()

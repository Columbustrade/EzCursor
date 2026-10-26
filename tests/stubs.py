"""Giả lập phần riêng của Windows để chạy kiểm thử trên Linux (cần màn hình ảo, vd xvfb)."""
import ctypes
import os
import sys
import tempfile
import types
from unittest import mock

ctypes.windll = mock.MagicMock()
ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
sys.modules["winreg"] = mock.MagicMock()
pt = types.ModuleType("pystray")
pt.Menu = mock.MagicMock()
pt.Menu.SEPARATOR = None
pt.captured = []


def _menu_item(text, *a, **k):
    pt.captured.append(text)


pt.MenuItem = _menu_item
pt.Icon = mock.MagicMock()
sys.modules["pystray"] = pt
os.environ.setdefault("APPDATA", os.path.join(tempfile.gettempdir(), "ezcursor-test-appdata"))

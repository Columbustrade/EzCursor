"""Giả lập phần riêng của Windows để chạy kiểm thử trên Linux (cần màn hình ảo, vd xvfb) hoặc Windows thật."""
import ctypes
import os
import sys
import tempfile
import types
from unittest import mock

# Luôn dùng thư mục tạm riêng: KHÔNG bao giờ để kiểm thử đụng tới %APPDATA%\EzCursor thật của người dùng
APPDATA = tempfile.mkdtemp(prefix="ezcursor-test-")
os.environ["APPDATA"] = APPDATA


def _dpi_for_monitor(monitor, dpi_type, px, py):
    px.contents.value = py.contents.value = 96      # 100%
    return 0


# Trên Windows thật customtkinter gọi windll lúc nạp font / tính DPI: phải trả số, không phải MagicMock
ctypes.windll = mock.MagicMock()
ctypes.windll.gdi32.AddFontResourceExW.return_value = 1
ctypes.windll.gdi32.AddFontResourceExA.return_value = 1
ctypes.windll.shcore.GetDpiForMonitor.side_effect = _dpi_for_monitor
ctypes.windll.shcore.SetProcessDpiAwareness.return_value = 0
ctypes.windll.user32.MonitorFromWindow.return_value = 1
ctypes.windll.user32.GetParent.return_value = 0
ctypes.windll.dwmapi.DwmSetWindowAttribute.return_value = 0
ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
sys.modules["winreg"] = mock.MagicMock()
sys.modules["winreg"].QueryValueEx.return_value = (0, 4)     # darkdetect (customtkinter) đọc AppsUseLightTheme: 0 = Dark
pt = types.ModuleType("pystray")
pt.Menu = mock.MagicMock()
pt.Menu.SEPARATOR = None
pt.captured = []


def _menu_item(text, *a, **k):
    pt.captured.append(text)


pt.MenuItem = _menu_item
pt.Icon = mock.MagicMock()
sys.modules["pystray"] = pt

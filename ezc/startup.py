"""Khởi động cùng Windows (khóa Run trong registry)."""

import sys
import winreg
from pathlib import Path

from .base import APP_NAME, ENTRY_SCRIPT


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    return f'"{exe}" "{ENTRY_SCRIPT}" --tray'


def run_value_exists(name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, name)
            return True
    except OSError:
        return False


def is_startup_enabled():
    return run_value_exists(APP_NAME)


def set_startup(on, name=APP_NAME):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(k, name)
            except OSError:
                pass

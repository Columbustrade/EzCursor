"""Phím tắt: đọc, chuẩn hóa và hiển thị tổ hợp phím."""

from .winapi import VK_CONTROL, VK_MENU, VK_SHIFT
from .system import key_down


HOTKEY_MODS = [("ctrl", VK_CONTROL, "Ctrl"), ("alt", VK_MENU, "Alt"), ("shift", VK_SHIFT, "Shift")]
HOTKEY_ACTIONS = ["toggle", "shape", "color", "quit", "find"]
_VK_NAMES = {0x20: "Space", 0x21: "PgUp", 0x22: "PgDn", 0x23: "End", 0x24: "Home", 0x2D: "Ins", 0x2E: "Del",
             0x13: "Pause", 0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
             0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'"}


def vk_name(vk):
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    if 0x60 <= vk <= 0x69:
        return f"Num{vk - 0x60}"
    return _VK_NAMES.get(vk, "")


HOTKEY_VKS = [v for v in list(range(0x30, 0x3A)) + list(range(0x41, 0x5B)) + list(range(0x60, 0x6A))
              + list(range(0x70, 0x88)) + list(_VK_NAMES)]


def hotkey_parts(binding, act):
    """Các phím để hiển thị, vd ['Ctrl', 'Alt', 'H']."""
    parts = [label for m, _, label in HOTKEY_MODS if m in binding["mods"]]
    return parts + (["1–5"] if act == "color" else [vk_name(binding["vk"])])


def mods_down():
    return {m for m, vk, _ in HOTKEY_MODS if key_down(vk)}

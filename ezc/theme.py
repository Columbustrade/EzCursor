"""Màu sắc, phông chữ của giao diện Neon HUD."""

import customtkinter as ctk

from .base import res_path


BG = "#0B0D12"
SIDEBAR = "#0D0F15"
CARD = "#12151D"
FIELD = "#0E1117"
BORDER = "#262B38"
LINE = "#1E2330"
TEXT = "#E8EAF0"
TEXT2 = "#A3ABBD"
MUTED = "#8B93A7"
ACCENT = "#FF1F8F"
CYAN = "#22D3EE"
CYAN_TEXT = "#67E8F9"
GREEN = "#3BE58F"
AMBER = "#FFB020"
SWATCHES = [("#FF1F8F", "Hồng neon"), ("#FF3B3B", "Đỏ"), ("#3BE58F", "Xanh lá"),
            ("#22D3EE", "Xanh cyan"), ("#FFD60A", "Vàng"), ("#A855F7", "Tím")]
# Ctrl+Alt+1..5 dùng 5 màu đầu
PRESET_COLORS = [c for c, _ in SWATCHES[:5]]

SHAPE_BUTTONS = [("Mũi tên", "Mũi tên"), ("Vòng tròn", "Vòng tròn"), ("Dấu thập", "Dấu thập"),
                 ("Chấm tròn", "Chấm tròn"), ("Kim cương", "Kim cương"), ("Ảnh tải lên", "Ảnh")]


def load_fonts():
    for f in ("ChakraPetch-Bold.ttf", "ChakraPetch-SemiBold.ttf",
              "BeVietnamPro-Regular.ttf", "BeVietnamPro-SemiBold.ttf"):
        p = res_path("fonts", f)
        if p.exists():
            try:
                ctk.FontManager.load_font(str(p))
            except Exception:
                pass


class Fonts:
    def __init__(self, root):
        import tkinter.font as tkfont
        fam = set(tkfont.families(root))
        self.head = "Chakra Petch" if "Chakra Petch" in fam else "Segoe UI"
        self.body = "Be Vietnam Pro" if "Be Vietnam Pro" in fam else "Segoe UI"
        self.body_b = "Be Vietnam Pro SemiBold" if "Be Vietnam Pro SemiBold" in fam else "Segoe UI Semibold"
        self.mono = "Consolas"

    def h(self, size, bold=True):
        return ctk.CTkFont(family=self.head, size=size, weight="bold" if bold else "normal")

    def b(self, size=13, strong=False):
        return ctk.CTkFont(family=self.body_b if strong else self.body, size=size)

    def m(self, size=11):
        return ctk.CTkFont(family=self.mono, size=size)

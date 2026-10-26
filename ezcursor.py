# -*- coding: utf-8 -*-
"""
EzCursor - con trỏ chuột tùy chỉnh cho game có con trỏ riêng (vd: Last Epoch)

- Giao diện Neon HUD (CustomTkinter)
- Tab "Ứng dụng": chọn ứng dụng đang chạy để áp dụng con trỏ, bấm Áp dụng
- Giao diện tiếng Việt / tiếng Anh (tab Tùy chọn > Ngôn ngữ)
- Bấm X: thu nhỏ xuống khay hệ thống. Thoát hẳn: menu khay hoặc Ctrl+Alt+Q
Phím tắt: Ctrl+Alt+H bật/tắt, Ctrl+Alt+R đổi con trỏ, Ctrl+Alt+F tìm con trỏ, Ctrl+Alt+1..5 đổi màu, Ctrl+Alt+Q thoát
Cài đặt lưu tại %APPDATA%\\EzCursor
"""
from ezc.app import main

if __name__ == "__main__":
    main()

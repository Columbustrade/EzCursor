# EzCursor

Con trỏ chuột tùy chỉnh (màu, hình dạng, ảnh riêng) cho các game có con trỏ khó nhìn như **Last Epoch**.
*Custom, high-visibility mouse cursor for games with hard-to-see cursors. English below.*

## Tải về

Vào mục [**Releases**](https://github.com/Columbustrade/EzCursor/releases/latest), tải file `EzCursor_Setup_x.x.x.exe` và chạy để cài đặt.

> Vì phần mềm chưa có chữ ký số, Windows có thể hiện cảnh báo *"Windows protected your PC"*. Bấm **More info → Run anyway** để tiếp tục.

## Tính năng

- Đổi màu, hình dạng (mũi tên, vòng tròn, dấu thập, chấm, kim cương) và kích thước con trỏ
- Dùng ảnh PNG của riêng bạn làm con trỏ, có thể tô màu cho ảnh
- Chỉ hiện trong những game / ứng dụng bạn chọn, ra ngoài thì con trỏ trở lại bình thường
- Chạy ngầm dưới khay hệ thống, có thể khởi động cùng Windows
- Tự kiểm tra và cập nhật phiên bản mới

## Cách dùng

1. Để game ở chế độ **Borderless** hoặc **Windowed** (không hoạt động ở Fullscreen độc quyền).
2. Mở game, mở EzCursor, vào tab **Ứng dụng** → **Làm mới danh sách** → chọn game → **Áp dụng**.
3. Chỉnh con trỏ ở tab **Con trỏ**. Bấm X để thu nhỏ xuống khay hệ thống.

| Phím tắt | Chức năng |
|---|---|
| Ctrl + Alt + H | Bật / tắt |
| Ctrl + Alt + R | Đổi hình dạng |
| Ctrl + Alt + 1..5 | Đổi màu |
| Ctrl + Alt + Q | Thoát |

**Nếu con trỏ chuột bị mất:** mở lại EzCursor rồi thoát bằng Ctrl + Alt + Q, hoặc đăng xuất / khởi động lại Windows.

## Lưu ý

EzCursor là một lớp phủ (overlay) chạy bên ngoài game: nó chỉ đọc vị trí chuột và vẽ con trỏ lên trên màn hình, **không** chỉnh sửa file hay can thiệp vào tiến trình của game. Tuy vậy, bạn tự chịu trách nhiệm tuân thủ điều khoản sử dụng của từng game.

## Tự build từ mã nguồn

Cần Python 3 (64-bit). Đặt các file cùng một thư mục rồi chạy `build_installer.bat`. File này sẽ cài thư viện, đóng gói `EzCursor.exe` bằng PyInstaller và tạo bộ cài bằng Inno Setup 6. Bộ cài nằm trong thư mục `installer`.

---

## English

**EzCursor** draws a customizable, high-visibility cursor (color, shape, size or your own PNG image) over selected games and apps, and hides the original cursor while the game is focused.

- Download the installer from [Releases](https://github.com/Columbustrade/EzCursor/releases/latest). If Windows SmartScreen appears, click **More info → Run anyway**.
- Run your game in **Borderless** or **Windowed** mode.
- In the **Ứng dụng** (Apps) tab, click **Làm mới danh sách** (Refresh), select your game and click **Áp dụng** (Apply).
- Hotkeys: Ctrl+Alt+H toggle, Ctrl+Alt+R next shape, Ctrl+Alt+1..5 colors, Ctrl+Alt+Q quit.
- EzCursor is an external overlay; it does not modify game files or memory. Use at your own discretion and follow each game's terms of service.

Licensed under the [MIT License](LICENSE).

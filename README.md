# EzCursor

Con trỏ chuột tùy chỉnh (màu, hình dạng, ảnh riêng) cho các game có con trỏ khó nhìn như **Last Epoch**.
*Custom, high-visibility mouse cursor for games with hard-to-see cursors. English below.*

## Tải về

Trang chủ: **https://ezcursor.github.io**

Vào mục [**Releases**](https://github.com/ezcursor/EzCursor/releases/latest), tải file `EzCursor_Setup_x.x.x.exe` và chạy để cài đặt.

> Vì phần mềm chưa có chữ ký số, Windows có thể hiện cảnh báo *"Windows protected your PC"*. Bấm **More info → Run anyway** để tiếp tục.

## Tính năng

- Đổi màu, hình dạng (mũi tên, vòng tròn, dấu thập, chấm, kim cương) và kích thước con trỏ
- **Con trỏ của bạn**: lưu nhiều ảnh PNG/GIF động hoặc file con trỏ Windows `.cur`, `.ani` trong Bộ sưu tập, bấm là dùng, có thể tô màu
- **Tìm con trỏ nhanh**: bấm Ctrl + Alt + F hoặc lắc chuột qua lại, con trỏ phóng to và tỏa vòng sáng
- **Kho con trỏ trực tuyến** (Bộ sưu tập → Trực tuyến): tải mẫu mới mà không cần cập nhật app
- **Con trỏ yêu thích**: bấm ☆ trên ô con trỏ, Ctrl + Alt + R chỉ đổi giữa các con trỏ yêu thích
- **Đổi nhanh từ khay hệ thống**: chuột phải icon EzCursor để chọn con trỏ hoặc hồ sơ game
- **Thiết lập lần đầu** 3 bước: chọn game, chọn con trỏ, xem phím tắt
- **Màu ombre**: con trỏ chuyển màu từ mũi ra đuôi (8 dải màu sẵn hoặc tự chọn), có thể cho dải màu chuyển động
- **Tạo con trỏ** ngay trong app: 10 hình, chỉnh dáng, một màu / ombre / kính mờ, viền, bóng đổ – lưu vào "Của bạn" và sửa lại bất cứ lúc nào
- **Bộ EzCursor** gồm 14 con trỏ phong cách game (Liquid Drop, Mảnh hồng, Tâm ngắm Neon, Mũi kiếm, Mũi tên Pha lê, Viên ngọc, Ký tự Rune, Cầu năng lượng, Ngọn lửa, Mũi giáo, Lông vũ, Ngôi sao, Mũi tên Bắn, Mũi tên Neon), dùng màu gốc hoặc đổi sang màu bất kỳ
- Bộ sưu tập con trỏ **Bibata** với các chủ đề Amber, Classic, Ice hoặc màu tùy chỉnh, kiểu Modern / Original, cho cả người thuận tay trái
- Chỉ hiện trong những game / ứng dụng bạn chọn, ra ngoài thì con trỏ trở lại bình thường; có sẵn gợi ý các game ARPG phổ biến
- Cảnh báo khi game đang chạy Fullscreen độc quyền
- Hồ sơ riêng cho từng game: mỗi game một con trỏ và hiệu ứng riêng, tự đổi khi chuyển game
- Viền màu tùy chọn khi giữ chuột trái (di chuyển) hoặc chuột phải (tung kỹ năng)
- Chạy ngầm dưới khay hệ thống, có thể khởi động cùng Windows
- Tự kiểm tra và cập nhật phiên bản mới
- Giao diện tiếng Việt hoặc tiếng Anh (tab **Tùy chọn → Ngôn ngữ**), đổi ngay không cần khởi động lại

## Cách dùng

1. Để game ở chế độ **Borderless** hoặc **Windowed** (không hoạt động ở Fullscreen độc quyền).
2. Lần đầu mở EzCursor, chọn game và con trỏ trong màn hình thiết lập nhanh. Thêm game sau này: mở game, vào tab **Ứng dụng** → **Làm mới** → chọn game → **Áp dụng**.
3. Chỉnh con trỏ ở tab **Con trỏ**. Bấm X để thu nhỏ xuống khay hệ thống.

| Phím tắt | Chức năng |
|---|---|
| Ctrl + Alt + H | Bật / tắt |
| Ctrl + Alt + R | Đổi con trỏ (giữa các con trỏ yêu thích nếu có) |
| Ctrl + Alt + 1..5 | Đổi màu |
| Ctrl + Alt + Q | Thoát |
| Ctrl + Alt + F | Tìm con trỏ (phóng to + vòng sáng) |

Có thể đổi phím tắt trong tab **Tùy chọn** (bấm vào ô phím tắt).

**Nếu gặp lỗi:** vào tab **Tùy chọn → Mở thư mục log** và gửi file `ezcursor.log` cho tác giả.

**Nếu con trỏ chuột bị mất:** mở lại EzCursor rồi thoát bằng Ctrl + Alt + Q, hoặc đăng xuất / khởi động lại Windows.

## Lưu ý

EzCursor là một lớp phủ (overlay) chạy bên ngoài game: nó chỉ đọc vị trí chuột và vẽ con trỏ lên trên màn hình, **không** chỉnh sửa file hay can thiệp vào tiến trình của game. Tuy vậy, bạn tự chịu trách nhiệm tuân thủ điều khoản sử dụng của từng game.

## Tự build từ mã nguồn

Cần Python 3 (64-bit). Đặt các file (kèm thư mục `fonts`) cùng một thư mục rồi chạy `build_installer.bat`. File này sẽ cài thư viện, đóng gói `EzCursor.exe` bằng PyInstaller và tạo bộ cài bằng Inno Setup 6. Bộ cài nằm trong thư mục `installer`.

### Cấu trúc mã nguồn

- `ezcursor.py`: điểm khởi chạy (chạy `python ezcursor.py` để mở app từ mã nguồn).
- `ezc/`: phần lõi, mỗi file một việc: `config.py` (cài đặt), `overlay.py` (lớp phủ vẽ con trỏ), `fx.py` (hiệu ứng), `ombre.py`, `maker.py` (trình tạo con trỏ), `curfile.py` (đọc .cur / .ani), `i18n.py` (ngôn ngữ), `syscursor.py` (chế độ Con trỏ thật, đang ẩn)...
- `ezc/ui/`: giao diện, mỗi file một phần của cửa sổ (tab Con trỏ, Bộ sưu tập, Hiệu ứng, Tùy chọn, menu khay, vòng lặp bám chuột...). Lớp `App` trong `ezc/app.py` ghép các phần này lại.
- Số phiên bản nằm trong `ezc/base.py` và `EzCursor.iss`.

### Kiểm thử

Thư mục `tests` chạy được trên Linux với màn hình ảo (phần riêng của Windows được giả lập): `xvfb-run -a python -m pytest tests`. GitHub tự chạy bộ kiểm thử này mỗi lần bạn Push (tab **Actions** của repo).

---

## English

**EzCursor** draws a customizable, high-visibility cursor (color, shape, size or your own PNG image) over selected games and apps, and hides the original cursor while the game is focused.

- Download the installer from [Releases](https://github.com/ezcursor/EzCursor/releases/latest). If Windows SmartScreen appears, click **More info → Run anyway**.
- Run your game in **Borderless** or **Windowed** mode.
- In the **Ứng dụng** (Apps) tab, click **Làm mới danh sách** (Refresh), select your game and click **Áp dụng** (Apply).
- Per-game profiles: give each game its own cursor and effects (Apps tab → "+ Own profile").
- Hotkeys: Ctrl+Alt+H toggle, Ctrl+Alt+R next cursor (favorites only once you star some), Ctrl+Alt+F find cursor, Ctrl+Alt+1..5 colors, Ctrl+Alt+Q quit (changeable in the Options tab).
- Library: EzCursor set, Bibata, your own cursors and an **Online** catalog of new designs; right-click the tray icon to switch cursors quickly.
- EzCursor is an external overlay; it does not modify game files or memory. Use at your own discretion and follow each game's terms of service.

EzCursor is licensed under the [GNU General Public License v3.0](LICENSE).

### Font

EzCursor đi kèm font [Chakra Petch](https://fonts.google.com/specimen/Chakra+Petch) và [Be Vietnam Pro](https://fonts.google.com/specimen/Be+Vietnam+Pro), phát hành theo giấy phép SIL Open Font License (xem các file `OFL-*.txt` trong thư mục `fonts`).

### Bộ con trỏ EzCursor

Các con trỏ trong `assets/ez` do EzCursor tự thiết kế, phát hành cùng giấy phép GPL-3.0. File vẽ nằm ở `tools/design_cursors.py`. Nguồn của kho con trỏ trực tuyến nằm ở `tools/catalog_src`, dựng bằng `tools/build_catalog.py` vào thư mục `catalog` của repo ezcursor.github.io.

### Bibata

Bộ sưu tập con trỏ trong EzCursor được tạo từ [Bibata Cursor](https://github.com/ful1e5/Bibata_Cursor) của **Abdulkaiz Khatri**, phát hành theo giấy phép GPL-3.0 (xem `bibata/LICENSE-Bibata.txt`). Ảnh trong thư mục `bibata` được chuyển từ các file SVG gốc của dự án này.

## Giấy phép

Từ phiên bản 1.2.0, EzCursor được phát hành theo giấy phép **GNU GPL v3.0** (xem file `LICENSE`).

# EzCursor

App Windows vẽ con trỏ chuột tùy biến (lớp phủ) cho game ARPG (Diablo, Path of Exile, Grim Dawn, Last Epoch). Python 3.13, customtkinter, pystray, Pillow. Giấy phép GPL-3.0.

- Repo app: ezcursor/EzCursor (repo này). Repo web: ezcursor/ezcursor.github.io (trang https://ezcursor.github.io + kho con trỏ `catalog/`).
- Đường dẫn repo web: laptop `..\Web_EzCursor\ezcursor.github.io`, PC `..\..\NewEzCursor\ezcursor.github.io`.
- Làm việc trên 2 máy (PC + laptop), đồng bộ qua GitHub: đầu phiên `git pull`, xong việc commit + push.
- Trả lời người dùng bằng tiếng Việt.

## Lệnh
- Cài thư viện (lần đầu): `py -3.13 -m pip install pillow pystray customtkinter pytest`
- Chạy app: thoát EzCursor đang chạy trước (Ctrl+Alt+Q, app chỉ cho 1 bản) rồi `py -3.13 ezcursor.py`
- Màn hình thiết lập lần đầu: `py -3.13 ezcursor.py --setup`
- Kiểm thử: Windows `py -3.13 -m pytest tests` (~2 phút); Linux `xvfb-run -a python -m pytest tests`; CI Linux chạy mỗi lần push (.github/workflows/tests.yml).
  - tests/stubs.py luôn đặt APPDATA về thư mục tạm mới (`tempfile.mkdtemp`); fixture `app` (tests/test_ui.py) assert đường dẫn nằm trong thư mục tạm đó trước khi `shutil.rmtree`. KHÔNG bỏ hai chốt này — trước đây test đã từng xoá `%APPDATA%\EzCursor` thật.
  - Sửa stubs: windll/winreg giả lập phải trả số thật (customtkinter/darkdetect dùng trên Windows); file mở trong test phải đóng ở teardown (Windows khoá file đang mở).
- Không bao giờ xoá/ghi đè `%APPDATA%\EzCursor` (config.json, my_cursors/) của người dùng. Trước khi chạy lệnh có thể đụng vào thư mục này, sao lưu nó trước.
- Log lỗi: `%APPDATA%\EzCursor\ezcursor.log`

## Cấu trúc mã nguồn
- `ezcursor.py` chỉ là điểm khởi chạy. Lõi ở gói `ezc/`, thứ tự phụ thuộc (module sau chỉ import module trước, không vòng lặp):
  base → winapi → syscursor → system → startup → i18n → hotkeys → config → colors → ombre → maker → curfile → display → theme → icons → bibata → shapes → overlay → fx
- Giao diện `ezc/ui/`: mỗi file một mixin (widgets, tray, profiles, cursor_tab, library, catalog_ui, maker_ui, effects, apps, options, hotkeys_ui, wizard, render, tracking, find, update, errors, syscursor_ui). `ezc/app.py` ghép thành `class App(...)` + `main()`.
- Thêm phương thức App → đặt vào mixin đúng nhóm. Thêm hàm lõi → đặt vào module đúng thứ tự.
- Tests: `tests/` dùng Windows giả lập (`tests/stubs.py`), `from harness import ez`, thay thế bằng `ez.X = ...`.

## Quy tắc bắt buộc
- Mọi chữ hiển thị mới: gọi qua `T("...")` và thêm bản dịch vào `TR_EN`. Ngôn ngữ hiện tại luôn đọc/ghi `i18n.LANG` (không import `LANG` trực tiếp). Kiểm tra cả Tiếng Việt và English.
- Cài đặt kiểu con trỏ mới (theo hồ sơ game): thêm vào `STYLE_KEYS` + `DEFAULT_CFG` + `clean_style`. Cài đặt chung: `DEFAULT_CFG` + kiểm tra trong `load_cfg`.
- Phím tắt mới: `HOTKEY_ACTIONS` + `DEFAULT_CFG["hotkeys"]` + `check_hotkeys` + names trong `hotkey_conflict` + ô trong tab Tùy chọn.
- Đặt ảnh con trỏ lên màn hình luôn qua `self.show_img()`.
- Ảnh con trỏ dựng trong `compose_cursor(outline, phase)`: ảnh gốc → ombre (`apply_ombre`) → viền giữ chuột → quầng sáng. Khung động dựng trong `build_cursor_frames` (24 khung).
- Menu khay: `build_tray_menu()` dựng lại khi trạng thái đổi. Action của pystray tối đa 2 tham số → dùng hàm tạo `act(cmd)`, không dùng lambda có tham số mặc định. Lệnh từ khay qua `self.q` tiền tố `tray_`, kho trực tuyến tiền tố `cat_`.
- File dùng CRLF; `EzCursor.iss` có BOM — giữ nguyên khi sửa.
- `AppUserModelID` giữ "Columbustrade.EzCursor" (không đổi).
- Chế độ "Con trỏ thật" (`ezc/syscursor.py`, `REAL_CURSOR_MODE = False`) đang ẩn có chủ ý — không bật nếu không được yêu cầu.

## Phát hành
1. Tăng `APP_VERSION` (ezc/base.py) và `MyAppVersion` (EzCursor.iss) — phải giống nhau.
2. Viết `release_notes.txt` (VI + EN).
3. Commit + push (sửa web/catalog thì push repo web trước).
4. Thoát EzCursor, chạy `build_installer.bat` → release lên ezcursor/EzCursor.
5. Kiểm tra: cài bản mới, tab Tùy chọn đúng số phiên bản, log không có ERROR.
6. winget (gói EzCursor.EzCursor): khai báo ở `tools/winget/<phiên bản>/` (phiên bản, link, SHA256) → `wingetcreate submit tools\winget\<phiên bản>`.
- Đã phát hành thì KHÔNG `--clobber` bộ cài (đổi SHA256 làm hỏng winget) — tăng phiên bản thay vì ghi đè.

## Kho con trỏ trực tuyến (không cần phát hành app)
- Nguồn: `tools/catalog_src/` (PNG 256 px nền trong suốt + `catalog-src.json`: id, src, hot, name vi/en, added).
- Build: `py -3.13 tools\build_catalog.py tools\catalog_src <repo web>\catalog` → commit + push cả 2 repo.
- Con trỏ của người khác: kiểm tra giấy phép trước khi đưa lên.

## Trang web (repo ezcursor.github.io)
- Thêm tính năng đáng kể → sửa danh sách tính năng/hướng dẫn trong `index.html` (VI) + bảng EN trong `main.js`.
- Sửa CSS/JS hoặc ảnh → tăng tham số `?v=` trong `index.html` / `main.js`.

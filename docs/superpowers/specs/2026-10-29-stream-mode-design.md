# Chế độ stream: hiện con trỏ EzCursor trên OBS

Ngày: 2026-10-29 · Trạng thái: đã duyệt

## Ý định

Khi livestream, OBS ghi game bằng **Game Capture**: chỉ có hình game vẽ và con trỏ hệ thống. Lớp phủ EzCursor nằm ngoài game nên **không lên stream**, còn con trỏ thật thì EzCursor đang ẩn, nên người xem có thể không thấy con trỏ nào. YoloMouse hiện được vì nó đổi chính con trỏ của game, nhưng cách đó phải chèn vào tiến trình game.

Chế độ stream cho người xem thấy **đúng con trỏ EzCursor mà người chơi đang thấy**, mà **không đụng vào game**: EzCursor chạy một trang web nhỏ trên máy, streamer thêm trang đó vào OBS bằng nguồn **Browser**, đặt trên Game Capture.

Dành cho: người chơi dùng EzCursor và tự stream bằng OBS Studio (Streamlabs Desktop dựa trên OBS nên cũng dùng được).

## Mục tiêu

- Người xem thấy lớp con trỏ y như trên màn hình người chơi: con trỏ tĩnh, ombre động, lấp lánh, viền khi giữ chuột trái/phải, vòng sáng "tìm con trỏ".
- Con trỏ trên stream ẩn/hiện cùng lúc với con trỏ trên màn hình (ra khỏi game, mở menu Start, tắt EzCursor... thì ẩn), và ẩn thêm khi chuột ra ngoài vùng game mà OBS ghi.
- Cài đặt dễ: bật một công tắc trong tab Tùy chọn, bấm "Sao chép link", dán vào nguồn Browser của OBS. Không mật khẩu, không plugin.
- Trang web và tài liệu hướng dẫn (README + trang ezcursor.github.io) có phần hướng dẫn OBS.

## Không làm (lần này)

- Vệt và hiệu ứng click (lớp hiệu ứng `fxw`): để bản sau; thiết kế không được chặn đường thêm vào.
- TikTok Live Studio và phần mềm stream không có nguồn Browser.
- Chế độ "Con trỏ thật" (`syscursor.py`): vẫn ẩn.

## Tuyệt đối tránh

- Bất cứ thứ gì chạm vào tiến trình game.
- Làm chậm hoặc làm khựng con trỏ trên màn hình người chơi (luồng bám chuột `CursorFollower`). Chế độ stream tắt thì gần như không tốn gì; bật thì mọi việc nặng (mã hóa PNG, gửi dữ liệu) chạy trên luồng riêng.
- Mở cổng ra mạng: máy chủ chỉ nghe `127.0.0.1`.
- Thêm thư viện ngoài hoặc làm bộ cài nặng thêm đáng kể: chỉ dùng thư viện chuẩn của Python.

## Ràng buộc của dự án

- Python, customtkinter; lõi ở `ezc/` theo thứ tự import một chiều, giao diện ở `ezc/ui/` (mixin) — xem `CLAUDE.md`.
- Mọi chữ hiển thị qua `T("...")` + bản dịch `TR_EN`; cài đặt chung thêm vào `DEFAULT_CFG` + kiểm tra trong `load_cfg` (không phải `STYLE_KEYS` — đây không phải cài đặt theo hồ sơ game).
- File CRLF. Test chạy với Windows giả lập (`tests/stubs.py`), cả trên Linux CI.
- Sửa web: `index.html` (VI) + bảng EN trong `main.js`, tăng `?v=`.

## Các cách đã cân nhắc

| Cách | Nội dung | Được | Mất |
|---|---|---|---|
| **A (đã chọn)** | EzCursor chạy máy chủ web cục bộ; OBS thêm trang bằng nguồn Browser; trang tự vẽ con trỏ từ ảnh + vị trí EzCursor gửi | Dán link là xong; hiện được con trỏ động; không thư viện ngoài | Cần một cổng mạng cục bộ, có thể trùng |
| B | EzCursor điều khiển OBS qua obs-websocket, dời một nguồn ảnh theo chuột | Không cần máy chủ riêng | Phải bật WebSocket + nhập mật khẩu; dời 60 lần/giây qua OBS dễ giật; con trỏ động gần như không làm được |
| C | Cửa sổ lớn nền xanh, OBS dùng Window Capture + Chroma Key | Không cần mạng | Cài đặt rườm rà; viền con trỏ lem màu xanh; thêm cửa sổ lớn chạy ngầm |

Người dùng chọn **A**.

## Thiết kế (đã thống nhất)

### Chỉ gương lớp con trỏ
Stream phản chiếu đúng **cửa sổ con trỏ** (`self.ovl`, thuộc `CursorFollower`): ảnh đang hiện, điểm click, đang ẩn hay hiện. Như vậy mọi thứ hiện ở lớp con trỏ (ảnh tĩnh, khung ombre/lấp lánh, biến thể giữ chuột, khung "tìm con trỏ") tự động lên stream mà không phải sửa từng nơi gọi.

### Thành phần

1. **`ezc/stream.py`** (lõi, đặt sau `overlay`/`fx` trong thứ tự import) — lớp `StreamServer`:
   - `ThreadingHTTPServer` của thư viện chuẩn, nghe `127.0.0.1:<cổng>`, chạy trên luồng nền riêng.
   - `GET /cursor` → trang HTML+JS (chuỗi nhúng sẵn trong mã, không file ngoài).
   - `GET /events` → luồng Server-Sent Events (một chiều EzCursor → trang). Trình duyệt tự kết nối lại khi rớt (`EventSource`).
   - `GET /img/<id>.png` → ảnh con trỏ đã mã hóa PNG.
   - Luồng giao diện chỉ gọi những hàm rất nhẹ (`publish_image(im, hot)`, `publish_visible(bool)`): ghi tham chiếu vào biến, không mã hóa, không chờ. Việc mã hóa PNG làm trên luồng máy chủ, **chỉ khi có trang đang kết nối**, có bộ nhớ đệm theo ảnh để khung ombre/lấp lánh lặp lại không phải mã hóa lại.
   - Vị trí chuột: luồng máy chủ tự đọc `GetCursorPos` ~60 lần/giây khi có trang kết nối và gửi khi thay đổi. Không dùng đoán trước vị trí (stream vốn trễ vài giây, không cần).

2. **Móc vào lớp con trỏ**: `CursorFollower`/`LayeredOverlay` báo cho `StreamServer` mỗi khi `set_image`, `show`, hoặc điểm click (`hot`/`find_hot`) đổi. Không có `StreamServer` thì không làm gì.

3. **Trang `/cursor`**: nền trong suốt, một `<canvas>` phủ kín trang; nhận sự kiện, vẽ ảnh con trỏ tại vị trí nhận được; ẩn khi EzCursor ẩn con trỏ.

### Tọa độ và tỉ lệ
- *(Quyết định của người viết, sau khi duyệt)* Vị trí gửi đi là **tỉ lệ 0..1 trong vùng nội dung (client area) của cửa sổ game đang ở trên cùng** (`GetClientRect` + `ClientToScreen`), kèm kích thước vùng đó. Game Capture của OBS ghi đúng vùng này, nên khớp cả khi game chạy Borderless (vùng nội dung = cả màn hình) lẫn Windowed. Fullscreen độc quyền thì EzCursor vốn không vẽ.
- Trang vẽ tại `x * chiều rộng trang`, và **phóng con trỏ theo tỉ lệ chiều rộng trang / chiều rộng vùng game**: game 2560 px, OBS 1920 px thì con trỏ nhỏ lại tương ứng, trông giống hệt người chơi thấy.
- *(Quyết định của người viết)* Chuột ra ngoài vùng game (sang màn hình khác, ra viền cửa sổ) thì **ẩn trên stream**, kể cả khi lớp phủ trên màn hình vẫn hiện: người xem không thấy vùng đó nên con trỏ ở mép hình chỉ gây rối. Tức là trên stream: hiện = lớp phủ đang hiện **và** chuột nằm trong vùng game.
- Giả định: nguồn Game Capture phủ kín khung OBS. Hướng dẫn ghi rõ: nguồn Browser đặt cùng kích thước khung OBS, nằm ngay trên Game Capture.
- *(Quyết định của người viết)* Nếu người chơi tắt "Ẩn con trỏ thật của game", OBS có thể ghi thêm con trỏ thật: hướng dẫn nhắc tắt "Capture Cursor" trong Game Capture.

### Cài đặt
- `DEFAULT_CFG`: `"stream": False`, `"stream_port": 47391`.
- Tab Tùy chọn: một dòng "Hiện con trỏ trên stream (OBS)" với công tắc; khi bật hiện link `http://127.0.0.1:<cổng>/cursor` và nút "Sao chép link", kèm một dòng hướng dẫn ngắn.
- Cổng bận: thử vài cổng kế tiếp, lưu cổng dùng được vào `stream_port` để link không đổi các lần sau; không được thì báo lỗi rõ ràng bằng `T(...)`.
- Thoát EzCursor (`App.quit`) thì tắt máy chủ.

### Kiểm thử
- Lõi: khởi động `StreamServer` trên cổng trống, `GET /cursor` trả trang; `/events` gửi sự kiện ảnh + vị trí + ẩn/hiện; `/img/...` trả PNG đúng kích thước; cổng bận thì chuyển cổng khác.
- Giao diện: bật/tắt công tắc nhiều lần không lỗi, không còn luồng/cổng treo; test bám chuột hiện có vẫn qua khi stream bật.

### Thứ tự phát hành *(quyết định của người viết)*
1. Làm và kiểm thử tính năng trong app, commit repo app (chưa phát hành).
2. Người dùng thử với OBS thật.
3. Thấy ổn mới phát hành (phiên bản mới, release notes, bộ cài, winget) **rồi** mới đưa hướng dẫn lên web/README, để trang web không giới thiệu công tắc mà người dùng chưa có.

## Để người làm tự quyết
- Định dạng chi tiết của sự kiện SSE và tên trường.
- Kích thước bộ nhớ đệm PNG, mức nén PNG, nhịp gửi vị trí chính xác.
- Bố cục chi tiết dòng cài đặt trong tab Tùy chọn và nội dung hướng dẫn trên web.

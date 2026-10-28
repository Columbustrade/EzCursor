# Chế độ stream (OBS) – kế hoạch thực hiện

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho OBS hiện đúng con trỏ EzCursor qua một trang web cục bộ (nguồn Browser), không đụng vào game.

**Architecture:** Module lõi mới `ezc/stream.py` chứa `StreamServer` (HTTP + Server-Sent Events của thư viện chuẩn, luồng riêng, chỉ nghe 127.0.0.1) và `OverlayMirror` (bọc cửa sổ con trỏ, chuyển mọi `set_image`/`show` sang `StreamServer`). Trang `/cursor` tự vẽ con trỏ trên canvas trong suốt. Giao diện bật/tắt ở mixin mới `ezc/ui/stream_ui.py`, dòng cài đặt trong tab Tùy chọn.

**Tech Stack:** Python (thư viện chuẩn `http.server`, `threading`, `json`), Pillow, customtkinter; HTML/JS thuần trong trang.

**Spec:** `docs/superpowers/specs/2026-10-29-stream-mode-design.md`

## Global Constraints

- Chỉ thư viện chuẩn của Python; không thêm gói vào `requirements.txt` / `build_installer.bat`.
- Máy chủ chỉ nghe `127.0.0.1`. Cổng mặc định `47391`; bận thì thử tối đa 10 cổng kế tiếp.
- Cài đặt chung: `"stream": False`, `"stream_port": 47391` trong `DEFAULT_CFG`, kiểm tra trong `load_cfg`; KHÔNG thêm vào `STYLE_KEYS`.
- Không việc nặng nào (mã hóa PNG, ghi socket) chạy trên luồng giao diện hay luồng bám chuột `CursorFollower`; `publish_*` chỉ gán biến.
- Mọi chữ hiển thị mới qua `T("...")` + bản dịch trong `TR_EN` (ezc/i18n.py).
- File CRLF; thứ tự import một chiều: `stream` đặt sau `fx` (chỉ import `base`, `winapi`).
- Chạy test: `py -3.15 -m pytest tests -q` (máy này không có 3.13); git là `%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe`.
- Vị trí gửi đi: tỉ lệ 0..1 trong vùng nội dung (client area) cửa sổ đang ở trên cùng; ngoài vùng đó thì ẩn trên stream.

## Review Focus

- Thoát EzCursor khi OBS đang kết nối: `stop()` phải xong < 2 giây, không treo vì kết nối SSE còn mở → test ở Task 1.
- OBS mở lại trang / hai nơi xem cùng lúc (khung preview + projector): mỗi kết nối đều nhận đủ ảnh hiện tại ngay khi vào → test ở Task 1.
- Ảnh đổi rất nhanh (hiệu ứng tìm con trỏ ~60 ảnh/giây): chỉ gửi ảnh mới nhất, không dồn hàng, ảnh cũ trùng `id()` không bị phát nhầm → test ở Task 1.
- Không có cửa sổ trên cùng / đọc vị trí lỗi (`locate()` trả `None`): ẩn trên stream, không văng lỗi → test ở Task 1.
- Bật/tắt công tắc liên tục: không còn cổng hay luồng treo, bật lại dùng được ngay → test ở Task 3.

---

### Task 1: `StreamServer` + trang `/cursor`

**Files:**
- Create: `ezc/stream.py`
- Test: `tests/test_stream.py`

**Interfaces:**
- Produces:
  - `StreamServer(port: int, locate: Callable[[], tuple[int, int, tuple[int, int, int, int]] | None], hot: Callable[[], tuple[int, int]])`
    - `locate()` → `(chuột x, chuột y, (trái, trên, rộng, cao) vùng game trên màn hình)` hoặc `None`.
    - `hot()` → điểm click hiện tại trong ảnh đang hiện.
  - `.start() -> int` (cổng thực dùng; thử `port`..`port+9`; hết thì `OSError`), `.stop() -> None`, `.url -> str` (`http://127.0.0.1:<cổng>/cursor`)
  - `.publish_image(im: PIL.Image.Image) -> None`, `.publish_visible(on: bool) -> None`
  - `game_view() -> tuple[int, int, tuple[int, int, int, int]] | None` – `locate` thật trên Windows (`GetCursorPos`, `GetForegroundWindow`, `GetClientRect`, `ClientToScreen`); vùng rộng/cao 0 thì `None`.
  - Giao thức (trang và test dựa vào, không đổi tên trường):
    - `GET /cursor` → HTML; `GET /img/<id>.png` → PNG; `GET /events` → `text/event-stream`.
    - `event: img` / `data: {"id": "<chuỗi>", "w": int, "h": int}` – gửi khi ảnh đổi và ngay khi một kết nối mới vào.
    - `event: pos` / `data: {"x": float, "y": float, "hx": int, "hy": int, "gw": int, "v": bool}` – x, y là tỉ lệ 0..1 trong vùng game; `gw` = chiều rộng vùng game (px); `v` = đang hiện **và** chuột trong vùng game. Gửi ~60 lần/giây khi có thay đổi, và ngay khi kết nối mới vào.

- [ ] **Step 1: Viết test (tests/test_stream.py)**

Dùng `from harness import ez` (nạp stubs), lấy cổng trống bằng `socket.bind(("127.0.0.1", 0))`. Helper `read_events(url, n, timeout=3)` mở `/events` bằng `http.client`, đọc theo dòng, trả về list `(event, dict)`.

```python
def test_page_image_and_position():
    s = ez.StreamServer(free_port(), locate=lambda: (960, 540, (0, 0, 1920, 1080)), hot=lambda: (5, 6))
    port = s.start()
    try:
        assert "EventSource" in get(f"http://127.0.0.1:{port}/cursor")
        s.publish_image(Image.new("RGBA", (32, 24), (255, 0, 0, 255)))
        s.publish_visible(True)
        ev = read_events(port, 2)
        img = next(d for e, d in ev if e == "img")
        pos = next(d for e, d in ev if e == "pos")
        assert (img["w"], img["h"]) == (32, 24)
        assert pos == {"x": 0.5, "y": 0.5, "hx": 5, "hy": 6, "gw": 1920, "v": True}
        png = Image.open(io.BytesIO(get_bytes(f"http://127.0.0.1:{port}/img/{img['id']}.png")))
        assert png.size == (32, 24)
    finally:
        s.stop()

def test_hidden_outside_game_or_no_window():     # chuột ngoài vùng game, hoặc locate() = None
    for loc in ((2500, 540, (0, 0, 1920, 1080)), None):
        ... publish_visible(True) -> sự kiện pos có "v": False

def test_busy_port_uses_next():                  # giữ cổng p bằng socket -> start() == p + 1

def test_stop_with_open_client_is_fast():        # mở /events, gọi stop(): xong < 2 s; bind lại cổng đó được

def test_two_clients_both_get_current_image():   # 2 kết nối /events, mỗi cái nhận event img cùng id

def test_rapid_images_send_latest():             # publish 50 ảnh khác kích thước liên tiếp rồi đọc:
                                                 # event img cuối cùng có kích thước của ảnh thứ 50
```

- [ ] **Step 2: Chạy test, phải fail**

Run: `py -3.15 -m pytest tests/test_stream.py -q`
Expected: FAIL (`AttributeError: StreamServer` từ harness).

- [ ] **Step 3: Viết `ezc/stream.py`**

- `ThreadingHTTPServer` (`daemon_threads = True`) + `BaseHTTPRequestHandler`, chạy `serve_forever` trên luồng daemon tên `"EzCursorStream"`. Bỏ log truy cập (`log_message` không làm gì).
- Một luồng phát (chỉ chạy khi có kết nối `/events`) mỗi ~16 ms: gọi `locate()`, `hot()`, so với lần gửi trước, ghi sự kiện cho mọi kết nối; kết nối lỗi thì bỏ. Mỗi kết nối SSE giữ handler trong vòng chờ cho tới khi `stop()` hoặc lỗi ghi.
- `publish_image`: gán `(số thứ tự tăng dần, ảnh)`; mã hóa PNG (`compress_level=1`) lười trên luồng máy chủ, bộ đệm theo số thứ tự (giữ ~64 ảnh gần nhất) – không dùng `id(im)` làm khóa.
- `stop()`: đánh dấu dừng, `shutdown()` + `server_close()`, đóng các socket SSE để handler thoát.
- Trang HTML nhúng là chuỗi trong module: nền trong suốt (`html, body {background: transparent; margin: 0; overflow: hidden}`), một `<canvas>` kích thước = `innerWidth × innerHeight` (cập nhật khi resize); `EventSource("/events")`; `img` → tải `/img/<id>.png`; vẽ lại theo `requestAnimationFrame` khi có thay đổi: `k = canvas.width / gw`, vẽ ảnh tại `(x * canvas.width - hx * k, y * canvas.height - hy * k)` kích thước `(w * k, h * k)`; `v` false thì xóa canvas.
- `game_view()` theo Interfaces; khai `argtypes`/`restype` cho các hàm user32 dùng tới.

- [ ] **Step 4: Chạy test, phải pass**

Run: `py -3.15 -m pytest tests/test_stream.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add ezc/stream.py tests/test_stream.py
git commit -m "Chế độ stream: StreamServer + trang /cursor cho OBS"
```

---

### Task 2: `OverlayMirror` – gương cửa sổ con trỏ

**Files:**
- Modify: `ezc/stream.py`
- Modify: `ezc/app.py` (chỗ `self.ovl = self.follow.ovl`)
- Test: `tests/test_stream.py`

**Interfaces:**
- Consumes: `StreamServer.publish_image`, `StreamServer.publish_visible` (Task 1).
- Produces:
  - `OverlayMirror(ovl)` – mọi thuộc tính khác (`hwnd`, `visible`, `move`, `raise_top`, `destroy`, `moves` của FakeOverlay…) chuyển thẳng tới `ovl` qua `__getattr__`.
  - `.set_image(im, pos=None)` → gọi `ovl.set_image(im, pos)` rồi, nếu `.target` khác `None`, `target.publish_image(im)`.
  - `.show(on)` → `ovl.show(on)` rồi `target.publish_visible(on)`.
  - `.target: StreamServer | None` (mặc định `None`); khi gán `target` mới, đẩy ngay ảnh cuối và trạng thái hiện hiện tại sang nó.
  - App: `self.ovl = OverlayMirror(self.follow.ovl)`.

- [ ] **Step 1: Viết test**

```python
def test_mirror_forwards_and_publishes():
    inner = FakeOv()                       # ghi lại set_image/show, có hwnd = 7
    m = ez.OverlayMirror(inner)
    im = Image.new("RGBA", (8, 8))
    m.set_image(im); m.show(True)          # chưa có target: chỉ chuyển tiếp
    assert inner.images == [im] and inner.visible and m.hwnd == 7
    target = Rec()                         # ghi lại publish_image / publish_visible
    m.target = target
    assert target.images == [im] and target.visible == [True]     # đẩy ngay trạng thái hiện tại
    m.show(False)
    assert target.visible == [True, False]
```

- [ ] **Step 2: Chạy test, phải fail** – `py -3.15 -m pytest tests/test_stream.py -q` → FAIL (`OverlayMirror`).
- [ ] **Step 3: Viết `OverlayMirror` trong `ezc/stream.py` và đổi `ezc/app.py` sang `self.ovl = OverlayMirror(self.follow.ovl)`.**
- [ ] **Step 4: Chạy toàn bộ test** – `py -3.15 -m pytest tests -q` → tất cả pass (test bám chuột cũ vẫn qua vì `moves` được chuyển tiếp).
- [ ] **Step 5: Commit** – `git commit -m "Chế độ stream: OverlayMirror gương cửa sổ con trỏ"`

---

### Task 3: Cài đặt, công tắc trong tab Tùy chọn, bật/tắt máy chủ

**Files:**
- Create: `ezc/ui/stream_ui.py` (`StreamMixin`)
- Modify: `ezc/app.py` (thêm `StreamMixin` vào `class App`, khởi động nếu `cfg["stream"]`, dừng trong `quit()`)
- Modify: `ezc/config.py` (`DEFAULT_CFG`, `load_cfg`)
- Modify: `ezc/ui/options.py` (dòng cài đặt, đặt sau dòng "Đoán trước vị trí con trỏ")
- Modify: `ezc/i18n.py` (`TR_EN`)
- Modify: `tests/test_core.py`, `tests/test_ui.py`

**Interfaces:**
- Consumes: `StreamServer`, `game_view` (Task 1); `OverlayMirror.target` (Task 2); `self.follow.find_hot`, `self.follow.hot`.
- Produces (StreamMixin):
  - `self.stream: StreamServer | None`
  - `start_stream() -> bool` – tạo `StreamServer(cfg["stream_port"], game_view, lambda: self.follow.find_hot or self.follow.hot)`, `start()`, lưu cổng thực vào `cfg["stream_port"]`, gán `self.ovl.target`; lỗi `OSError` thì ghi log, báo `messagebox` bằng `T(...)`, trả `False`.
  - `stop_stream() -> None` – `self.ovl.target = None`, `stop()`, `self.stream = None`.
  - `set_stream()` – callback công tắc: đọc `self.stream_var`, bật/tắt, cập nhật `cfg["stream"]` (bật lỗi thì trả công tắc về tắt), `save()`, cập nhật dòng link.
  - `copy_stream_link()` – `self.win.clipboard_clear(); self.win.clipboard_append(self.stream.url)`.
- Chữ mới (VI → EN), thêm đúng các khóa này vào `TR_EN`:
  - "Hiện con trỏ trên stream (OBS)" → "Show cursor on stream (OBS)"
  - "Thêm nguồn Browser trong OBS với link này, đặt trên Game Capture." → "Add a Browser source in OBS with this link, above Game Capture."
  - "Sao chép link" → "Copy link"
  - "Không mở được chế độ stream:" → "Couldn't start stream mode:"

- [ ] **Step 1: Viết test**

```python
# tests/test_core.py
def test_stream_cfg_defaults_and_repair(tmp_path, monkeypatch):
    # DEFAULT_CFG có stream False, stream_port 47391
    # config.json {"stream": "x", "stream_port": 99999} -> load_cfg trả stream False, stream_port 47391
    # {"stream": True, "stream_port": 47395} giữ nguyên

# tests/test_ui.py
def test_stream_toggle(app):
    for _ in range(3):
        app.stream_var.set(True); app.set_stream(); pump(app, 3)
        assert app.stream is not None and app.cfg["stream"]
        assert "EventSource" in urllib.request.urlopen(app.stream.url, timeout=3).read().decode()
        app.stream_var.set(False); app.set_stream(); pump(app, 3)
        assert app.stream is None and not app.cfg["stream"]
    app.set_language("en"); pump(app)          # dòng cài đặt dựng lại được ở tiếng Anh
    assert not log_errors()
```

- [ ] **Step 2: Chạy test, phải fail** – `py -3.15 -m pytest tests -q` → 2 test mới FAIL.
- [ ] **Step 3: Thêm cấu hình (`DEFAULT_CFG` + kiểm tra trong `load_cfg`: `stream` ép `bool`, `stream_port` là int trong 1024..65535, sai thì 47391).**
- [ ] **Step 4: Viết `StreamMixin`, thêm vào `App`; trong `App.__init__` sau khi dựng giao diện: `self.stream = None` và nếu `cfg["stream"]` thì `start_stream()`; `quit()` gọi `stop_stream()` trước `self.follow.stop()`.**
- [ ] **Step 5: Dòng cài đặt trong `options.py`:** cùng kiểu với các dòng công tắc sẵn có (`self.switch(...)`); bên dưới, khi bật, một nhãn link (font `self.F.m`) + `self.cyan_button(r, "Sao chép link", self.copy_stream_link)` + dòng hướng dẫn; khi tắt thì ẩn phần link. Thêm 4 chuỗi vào `TR_EN`.
- [ ] **Step 6: Chạy toàn bộ test** – `py -3.15 -m pytest tests -q` → tất cả pass. Chạy thêm 3 lần để chắc không có test chập chờn.
- [ ] **Step 7: Commit** – `git commit -m "Chế độ stream: công tắc và link trong tab Tùy chọn"`

---

### Task 4: Kiểm tra trên máy thật và ghi chú README

**Files:**
- Modify: `README.md` (thêm mục tính năng + "Hiện con trỏ khi livestream (OBS)" ở phần VI và EN)

- [ ] **Step 1: Sao lưu `%APPDATA%\EzCursor` vào scratchpad, thoát EzCursor đang chạy, chạy `py -3.15 ezcursor.py`.**
- [ ] **Step 2: Bật công tắc, mở link trong trình duyệt:** trang trong suốt, không lỗi trong console (`read_console_messages`); bấm "Sao chép link" có link đúng cổng.
- [ ] **Step 3: Kiểm tra log** `%APPDATA%\EzCursor\ezcursor.log` không có ERROR; thoát app nhanh, không treo.
- [ ] **Step 4: README** – thêm một gạch đầu dòng tính năng và mục hướng dẫn 4 bước: bật công tắc → OBS: Add → Browser → dán link, chiều rộng/cao bằng khung OBS → đặt trên Game Capture → (nếu tắt "Ẩn con trỏ thật của game") tắt "Capture Cursor" của Game Capture. Chưa sửa web (theo thứ tự phát hành trong spec).
- [ ] **Step 5: Commit** – `git commit -m "README: hướng dẫn chế độ stream với OBS"`
- [ ] **Step 6: Bàn giao cho người dùng thử với OBS thật** (game Borderless + Game Capture; đổi con trỏ, giữ chuột, Ctrl+Alt+F, rê sang màn hình khác) trước khi phát hành và sửa web.

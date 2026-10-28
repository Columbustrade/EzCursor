"""Giao diện tiếng Việt / tiếng Anh."""


LANGUAGES = [("vi", "Tiếng Việt"), ("en", "English")]
LANG = "vi"          # đổi qua App.set_language
# Bảng dịch Việt -> Anh. Chuỗi tiếng Việt là khóa; thiếu khóa thì giữ nguyên tiếng Việt.
TR_EN = {
    # Thanh bên & khay hệ thống
    "Con trỏ": "Cursor", "Bộ sưu tập": "Library", "Hiệu ứng": "Effects", "Ứng dụng": "Apps",
    "Tùy chọn": "Options", "TRẠNG THÁI": "STATUS", "Bật EzCursor": "Enable EzCursor",
    "Mở EzCursor": "Open EzCursor", "Bật con trỏ": "Enable cursor", "Kiểm tra cập nhật": "Check for updates",
    "Thoát": "Quit",
    # Tab Con trỏ
    "CON TRỎ": "CURSOR",
    "Chọn hình dạng, màu sắc và kích thước con trỏ trong game.": "Choose the shape, color and size of your in-game cursor.",
    "XEM TRƯỚC": "PREVIEW", "HÌNH DẠNG": "SHAPE", "MÀU SẮC": "COLOR", "KÍCH THƯỚC": "SIZE",
    "ẢNH TÙY CHỈNH": "CUSTOM IMAGE", "Tải ảnh lên": "Upload image", "(chưa có ảnh)": "(no image)",
    "Điểm click": "Click point", "Giữa ảnh": "Center", "Góc trên trái": "Top-left",
    "Tô màu cho ảnh tải lên": "Tint uploaded image", "Quầng sáng quanh con trỏ": "Glow around cursor",
    "Mũi tên": "Arrow", "Vòng tròn": "Circle", "Dấu thập": "Cross", "Chấm tròn": "Dot",
    "Kim cương": "Diamond", "Ảnh": "Image",
    # Tab Bộ sưu tập
    "BỘ SƯU TẬP": "LIBRARY",
    "Con trỏ của EzCursor và bộ Bibata. Bấm vào con trỏ muốn dùng.": "EzCursor's own cursors and the Bibata set. Click a cursor to use it.",
    "Không tìm thấy thư mục bibata đi kèm phần mềm.": "The bundled bibata folder was not found.",
    "CHỦ ĐỀ": "THEME", "Tùy chỉnh": "Custom", "MÀU TÙY CHỈNH": "CUSTOM COLOR",
    "Modern · bo tròn": "Modern · rounded", "Original · góc nhọn": "Original · sharp",
    "Thuận tay phải": "Right-handed", "Thuận tay trái": "Left-handed",
    "Chọn một màu để chuyển sang chủ đề Tùy chỉnh.": "Pick a color to switch to the Custom theme.",
    "Chọn màu": "Choose color", "Mảnh hồng": "Pink Shard",
    "Mũi tên ngược": "Reverse arrow", "Mũi tên đứng": "Upright arrow", "Bàn tay chỉ": "Pointing hand",
    "Bàn tay mở": "Open hand", "Nắm tay": "Grabbing", "Tâm ngắm": "Crosshair", "Thập mảnh": "Thin cross",
    "Dấu cộng": "Plus", "Ô chấm": "Dot box", "Dấu X": "X", "Bút chì": "Pencil",
    # Tab Hiệu ứng
    "HIỆU ỨNG": "EFFECTS",
    "Thêm vệt sáng theo con trỏ và hiệu ứng khi click trong game.": "Add a glowing trail behind the cursor and click effects in game.",
    "VỆT THEO CON TRỎ": "CURSOR TRAIL", "KHI CLICK CHUỘT TRÁI": "ON LEFT CLICK", "QUANH CON TRỎ": "AROUND CURSOR",
    "Tắt": "Off", "Lấp lánh": "Sparkle", "Vệt neon": "Neon trail", "Cầu vồng": "Rainbow",
    "Bóng mờ": "Ghost", "Bong bóng": "Bubbles", "Gợn sóng": "Ripple", "Pháo hoa": "Fireworks",
    "Theo màu con trỏ": "Match cursor color", "Ba màu EzCursor": "EzCursor tri-color",
    "Ít": "Low", "Vừa": "Medium", "Nhiều": "High", "Màu hiệu ứng": "Effect color", "Mật độ": "Density",
    "THỬ NGAY TRÊN MÀN HÌNH": "TRY IT ON SCREEN", "ĐANG THỬ...": "TESTING...",
    "   Di chuột và click trong 8 giây để xem hiệu ứng.": "   Move and click the mouse for 8 seconds to see the effects.",
    "Hãy chọn ít nhất một hiệu ứng trước khi thử.": "Please select at least one effect before testing.",
    # Tab Ứng dụng
    "ỨNG DỤNG": "APPS",
    "Chọn game sẽ dùng con trỏ của EzCursor, rồi bấm Áp dụng.": "Select the games that will use the EzCursor cursor, then click Apply.",
    "Làm mới": "Refresh", "  Áp dụng cho mọi ứng dụng (kể cả Desktop)": "  Apply to all apps (including Desktop)",
    "ÁP DỤNG": "APPLY", "(đang không chạy)": "(not running)", " ĐANG CHẠY ": " RUNNING ",
    " KHÔNG CHẠY ": " NOT RUNNING ", "Đang áp dụng cho: ": "Applied to: ",
    "Chưa chọn ứng dụng nào.": "No apps selected.", "✓ Đã áp dụng.  ": "✓ Applied.  ",
    # Tab Tùy chọn
    "TÙY CHỌN": "OPTIONS", "Cài đặt chung, cập nhật và phím tắt.": "General settings, updates and hotkeys.",
    "Ngôn ngữ": "Language", "Ngôn ngữ hiển thị của EzCursor.": "Display language of EzCursor.",
    "Ẩn con trỏ thật của game": "Hide the game's real cursor",
    "Chỉ hiện con trỏ của EzCursor khi đang ở trong game.": "Show only the EzCursor cursor while in game.",
    "Khởi động cùng Windows": "Start with Windows",
    "Chạy ngầm dưới khay hệ thống khi bật máy.": "Run in the system tray when your PC starts.",
    "Tự động kiểm tra cập nhật": "Check for updates automatically",
    "Thông báo khi có phiên bản mới trên GitHub.": "Notify when a new version is on GitHub.",
    "Màn hình chào khi mở": "Splash screen on launch",
    "Hiện logo động khoảng 2 giây mỗi lần mở EzCursor.": "Show the animated logo for about 2 seconds at launch.",
    "Phiên bản ": "Version ", "Khôi phục cài đặt gốc": "Reset to defaults",
    "Xóa mọi lựa chọn đã lưu và khởi động lại EzCursor như mới cài.": "Clear all saved settings and restart EzCursor as freshly installed.",
    "Khôi phục": "Reset", "PHÍM TẮT": "HOTKEYS", "Bật / tắt": "On / off", "Đổi hình dạng": "Change shape",
    "Đổi màu": "Change color",
    # Trạng thái
    "●  ĐANG TẮT": "●  OFF", "Con trỏ gốc đang được dùng.": "The default cursor is in use.",
    "Áp dụng cho mọi ứng dụng.": "Applied to all apps.", "Trong game: ": "In game: ",
    "●  ĐANG HOẠT ĐỘNG": "●  ACTIVE", "●  TẠM DỪNG": "●  PAUSED",
    "Đang ở trên giao diện của Windows.": "Over a Windows interface.",
    "●  CHƯA CHỌN GAME": "●  NO GAME SELECTED", "Vào tab Ứng dụng để chọn game.": "Go to the Apps tab to pick a game.",
    "●  ĐANG CHỜ GAME": "●  WAITING FOR GAME", "Chờ: ": "Waiting: ",
    # Hộp thoại & thông báo
    "Lỗi": "Error", "Không thay đổi được cài đặt khởi động:": "Could not change the startup setting:",
    "Chọn ảnh con trỏ": "Choose a cursor image", "Tất cả": "All files",
    "Không sao chép được ảnh:": "Could not copy the image:", "Không mở được ảnh:": "Could not open the image:",
    "EzCursor vẫn đang chạy dưới khay hệ thống. Chuột phải vào icon để mở lại hoặc thoát.":
        "EzCursor is still running in the system tray. Right-click the icon to reopen or quit.",
    "Khôi phục toàn bộ cài đặt về mặc định?\n\nDanh sách game, con trỏ, hiệu ứng và ảnh đã tải lên sẽ bị xóa. EzCursor sẽ tự khởi động lại.":
        "Reset all settings to defaults?\n\nYour game list, cursor, effects and uploaded image will be removed. EzCursor will restart automatically.",
    "Chưa cấu hình GITHUB_REPO trong mã nguồn.": "GITHUB_REPO is not configured in the source code.",
    "Đang kiểm tra cập nhật...": "Checking for updates...",
    "Bạn đang dùng phiên bản mới nhất.": "You are using the latest version.",
    "Bạn đang dùng phiên bản mới nhất": "You are using the latest version",
    "Có phiên bản mới: ": "New version available: ",
    "Đã có EzCursor {v}. Mở EzCursor để cập nhật.": "EzCursor {v} is available. Open EzCursor to update.",
    "Không kiểm tra được cập nhật.": "Could not check for updates.",
    "Không kiểm tra được cập nhật.\nHãy kiểm tra kết nối mạng.": "Could not check for updates.\nPlease check your internet connection.",
    "Đang tải...": "Downloading...",
    "Đang cài đặt, EzCursor sẽ tự mở lại sau giây lát...": "Installing, EzCursor will reopen in a moment...",
    "Không chạy được bộ cài:": "Could not run the installer:", "Tải về thất bại.": "Download failed.",
    "Tải bản cập nhật thất bại:": "Failed to download the update:", "File tải về không đầy đủ hoặc bị lỗi, hãy thử lại.": "The download is incomplete or damaged, please try again.", "Cập nhật": "Update",
    "CÓ PHIÊN BẢN MỚI": "NEW VERSION AVAILABLE", "   (bạn đang dùng {v})": "   (you have {v})",
    "CÓ GÌ MỚI": "WHAT'S NEW", "(không có ghi chú)": "(no release notes)", "CẬP NHẬT NGAY": "UPDATE NOW",
    "MỞ TRANG TẢI VỀ": "OPEN DOWNLOAD PAGE", "Để sau": "Later", "Bỏ qua phiên bản này": "Skip this version",
    # 1.5.0
    "Theo file": "From file", "Phóng theo tỉ lệ màn hình": "Scale with display",
    "GỢI Ý: GAME ARPG PHỔ BIẾN": "SUGGESTED: POPULAR ARPGS", " GỢI Ý ": " SUGGESTED ",
    "●  FULLSCREEN": "●  FULLSCREEN",
    "Game đang ở Fullscreen. Hãy chuyển sang Borderless hoặc Windowed.":
        "The game is in Fullscreen. Switch it to Borderless or Windowed.",
    "Game đang chạy Fullscreen nên EzCursor không vẽ được con trỏ. "
    "Hãy chuyển game sang Borderless hoặc Windowed trong phần cài đặt đồ họa.":
        "The game is running in Fullscreen, so EzCursor can't draw the cursor. "
        "Switch the game to Borderless or Windowed in its graphics settings.",
    "Ảnh hoặc con trỏ": "Images or cursors", "Con trỏ Windows": "Windows cursors",
    "Mặc định": "Defaults", "Bấm vào một ô để đổi phím": "Click a box to change it",
    "Đổi phím tắt": "Change hotkey", "Nhấn tổ hợp phím mới": "Press the new key combination",
    "Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím số từ 1 đến 5.":
        "Hold Ctrl or Alt (optionally with Shift) and press a number key from 1 to 5.",
    "Nhấn Ctrl hoặc Alt (có thể thêm Shift) cùng một phím chữ, số hoặc F1–F12.":
        "Hold Ctrl or Alt (optionally with Shift) and press a letter, number or F1–F12 key.",
    "Bấm Esc để hủy.": "Press Esc to cancel.", "Cần giữ Ctrl hoặc Alt.": "Hold Ctrl or Alt.",
    "Đổi màu dùng các phím số 1–5.": "Color changes use number keys 1–5.",
    "Trùng với phím của: ": "Already used by: ",
    # 1.6.0
    "Đang chỉnh": "Editing", "Mặc định (mọi game)": "Default (all games)",
    # 1.9.0
    "Đổi con trỏ": "Change cursor", "Hình cơ bản": "Basic shapes", "Con trỏ của bạn": "Your cursors",
    "(chưa có)": "(none yet)", "Hồ sơ": "Profile", "Áp cho: {n}": "Applies to: {n}",
    "Yêu thích": "Favorites", "Thêm vào Yêu thích": "Add to favorites", "Bỏ khỏi Yêu thích": "Remove from favorites",
    "Bấm ☆ để thêm vào Yêu thích. Ctrl+Alt+R sẽ chỉ đổi giữa các con trỏ yêu thích.":
        "Click ☆ to add a favorite. Ctrl+Alt+R then cycles through your favorites only.",
    "THIẾT LẬP NHANH": "QUICK SETUP", "Bước {i} / 3": "Step {i} / 3", "Bỏ qua": "Skip", "Quay lại": "Back",
    "Tiếp tục": "Next", "Bắt đầu": "Let's go",
    "Bạn chơi game nào?": "Which games do you play?",
    "EzCursor chỉ hiện con trỏ khi các game này đang mở. Có thể đổi sau ở tab Ứng dụng.":
        "EzCursor only shows its cursor while these games are open. You can change this later in the Apps tab.",
    "Chọn con trỏ": "Pick a cursor",
    "Chọn con trỏ bạn thích. Bộ sưu tập còn bộ Bibata và chỗ thêm con trỏ của riêng bạn.":
        "Pick the cursor you like. The Library also has the Bibata set and room for your own cursors.",
    "Nhỏ": "Small", "Vừa": "Medium", "Lớn": "Large",
    "Sẵn sàng!": "All set!",
    "Mở game là con trỏ mới sẽ hiện. Vài phím tắt nên nhớ:": "Open your game and the new cursor appears. A few handy hotkeys:",
    "Đổi con trỏ (giữa các con trỏ yêu thích)": "Change cursor (between favorites)",
    "Tìm con trỏ (hoặc lắc chuột)": "Find cursor (or shake the mouse)",
    "EzCursor chạy ở khay hệ thống. Chuột phải vào icon để đổi nhanh con trỏ hoặc hồ sơ.":
        "EzCursor lives in the system tray. Right-click its icon to quickly change cursor or profile.",
    "Game": "Games", "Mọi ứng dụng": "All applications", "(chưa chọn)": "(none selected)",
    "Trực tuyến": "Online", "Làm mới": "Refresh", "Đang tải danh sách…": "Loading the list…",
    "{n} con trỏ · Bấm để tải về, con trỏ sẽ nằm trong mục Của bạn.":
        "{n} cursors · Click to download; it will be added to Yours.",
    "Không kết nối được kho trực tuyến. Kiểm tra mạng rồi bấm Làm mới.":
        "Couldn't reach the online catalog. Check your connection and click Refresh.",
    "Đang xem danh sách lưu lần trước (chưa kết nối được).": "Showing the last saved list (offline).",
    "Tải về": "Download", "Đang tải…": "Downloading…", "✓ Đã có": "✓ Added", "MỚI": "NEW",
    "Không tải được con trỏ:": "Couldn't download the cursor:",
    "File không khớp mã kiểm tra": "Checksum mismatch", "File con trỏ bị lỗi": "The cursor file is damaged",
    "File quá lớn": "File too large",
    "MÀU OMBRE": "OMBRE", "  Chuyển động": "  Animate", "Chậm": "Slow", "Nhanh": "Fast",
    "Hoàng hôn": "Sunset", "Đại dương": "Ocean", "Lửa": "Fire", "Độc dược": "Toxic", "Băng giá": "Frost",
    "Hư không": "Void", "Cầu vồng": "Rainbow", "Tự chọn": "Custom", "Tự chọn màu ombre": "Custom ombre",
    "Màu 1 ở mũi con trỏ, màu cuối ở đuôi.": "Color 1 is at the cursor tip, the last color at the tail.",
    "Dùng 3 màu": "Use 3 colors", "Dùng dải màu này": "Use these colors", "Hủy": "Cancel",
    "✦ Tạo con trỏ": "✦ Create cursor", "Tạo con trỏ": "Create cursor", "TẠO CON TRỎ": "CREATE A CURSOR",
    "Chọn hình, chỉnh dáng, màu và viền. Con trỏ được lưu vào mục Của bạn.":
        "Pick a shape, then tune its form, colors and outline. It's saved to Yours.",
    "Bấm vào hình để đặt điểm click": "Click the image to set the click point",
    "Điểm click tự động": "Auto click point", "KÍCH THƯỚC THẬT": "ACTUAL SIZE", "HÌNH DÁNG": "SHAPE",
    "DÁNG": "FORM", "Độ rộng": "Width", "Độ dài đuôi": "Tail length", "Độ dày nét": "Thickness", "Bo góc": "Roundness",
    "Xoay": "Rotation", "Khe hở": "Gap", "TÔ MÀU": "FILL", "Một màu": "Solid", "Kính mờ": "Glass", "VIỀN": "OUTLINE",
    "Viền trong": "Inner outline", "Viền ngoài": "Outer outline", "CHI TIẾT": "DETAILS",
    "Chấm sáng ở mũi": "Tip dot", "Vệt sáng": "Shine", "Bóng đổ": "Shadow", "Tên": "Name",
    "Con trỏ của tôi": "My cursor", "Lưu vào Của bạn": "Save to Yours", "Không lưu được con trỏ:": "Couldn't save the cursor:",
    "Sửa con trỏ này": "Edit this cursor",
    "Nhọn": "Sharp", "Bo tròn": "Rounded", "Mảnh": "Slim", "Pha lê": "Shard", "Giọt nước": "Droplet",
    "Tam giác": "Triangle", "Chấm": "Dot", "Vòng": "Ring",
    "Chưa có con trỏ nào. Tự tạo một con trỏ, hoặc bấm \"+ Thêm con trỏ\" để thêm ảnh PNG, GIF hay file .cur, .ani.":
        "No cursors yet. Create one, or click \"+ Add cursor\" to add a PNG, GIF, .cur or .ani file.",
    "{g} dùng con trỏ riêng của game nên chế độ Con trỏ thật không đổi được. EzCursor đã chuyển sang Lớp phủ cho game này.":
        "{g} uses its own cursor, so Real cursor mode can't replace it. EzCursor switched to Overlay for this game.",
    "Game này dùng con trỏ riêng và đang chạy Fullscreen nên EzCursor không thể hiện con trỏ. Hãy chuyển game sang Borderless hoặc Windowed.":
        "This game uses its own cursor and runs in exclusive Fullscreen, so EzCursor can't show its cursor. Switch the game to Borderless or Windowed.",
    "Giữ con trỏ trên thanh taskbar": "Keep cursor on the taskbar",
    "Rê chuột xuống taskbar vẫn dùng con trỏ EzCursor.": "Keep the EzCursor cursor when you move over the taskbar.",
    "Hiện con trỏ trên stream (OBS)": "Show cursor on stream (OBS)",
    "Cho người xem stream thấy con trỏ EzCursor qua nguồn Browser của OBS.":
        "Let stream viewers see your EzCursor cursor through an OBS Browser source.",
    "Dán link vào nguồn Browser của OBS: ": "Paste this link into an OBS Browser source: ",
    "Sao chép link": "Copy link",
    "Không mở được chế độ stream:": "Couldn't start stream mode:",
    "Đoán trước vị trí con trỏ": "Predict cursor position",
    "Bù thêm nửa khung hình khi rê nhanh; có thể trượt nhẹ khi đổi hướng.":
        "Gains half a frame on fast moves; may overshoot slightly when you change direction.",
    "Chế độ con trỏ": "Cursor mode", "Lớp phủ": "Overlay", "Con trỏ thật": "Real cursor",
    "Không độ trễ, chạy cả Fullscreen. Không có lấp lánh, ombre chuyển động.":
        "Zero lag, works in Fullscreen too. No sparkle or animated ombre.",
    "Đủ hiệu ứng. Game cần chạy Borderless hoặc Windowed.": "All effects. The game must run Borderless or Windowed.",
    "Game đang chạy Fullscreen nên EzCursor không vẽ được con trỏ. Hãy chuyển game sang Borderless hoặc Windowed, "
    "hoặc bật chế độ \"Con trỏ thật\" trong tab Tùy chọn.":
        "The game is running in exclusive Fullscreen, so EzCursor can't draw its cursor. Switch the game to "
        "Borderless or Windowed, or turn on \"Real cursor\" mode in the Options tab.",
    "Của bạn": "Yours", "Tô màu": "Tinted", "+ Thêm con trỏ": "+ Add cursor", "Xóa con trỏ này": "Delete this cursor",
    "Xóa con trỏ \"{n}\" khỏi bộ sưu tập?": "Remove the cursor \"{n}\" from your library?",
    "Chưa có con trỏ nào. Bấm \"+ Thêm con trỏ\" để thêm ảnh PNG, GIF hoặc file con trỏ .cur, .ani.":
        "No cursors yet. Click \"+ Add cursor\" to add a PNG, GIF or .cur / .ani cursor file.",
    "Tìm con trỏ": "Find cursor", "Lắc chuột để tìm": "Shake to find",
    # 1.8.0
    "Bộ EzCursor": "EzCursor set", "Màu gốc": "Original",
    "Tâm ngắm Neon": "Neon Crosshair",
    "Mũi kiếm": "Blade",
    "Mũi tên Pha lê": "Crystal Arrow",
    "Viên ngọc": "Gem",
    "Ký tự Rune": "Rune",
    "Cầu năng lượng": "Energy Orb",
    "Ngọn lửa": "Flame",
    "Mũi giáo": "Spear",
    "Lông vũ": "Feather",
    "Ngôi sao": "Star",
    "Mũi tên Bắn": "Arrow Shot",
    "Mũi tên Neon": "Neon Arrow",
    # 1.7.0
    "Viền khi giữ chuột": "Outline while holding", "Trái": "Left", "Phải": "Right",
    "Chọn màu viền": "Choose outline color", "Mở thư mục log": "Open log folder",
    "EzCursor gặp lỗi liên tục nên đã tạm tắt con trỏ để bạn dùng chuột bình thường. "
    "Hãy mở lại EzCursor; chi tiết lỗi nằm trong file ezcursor.log.":
        "EzCursor kept hitting errors, so it turned its cursor off to keep your mouse usable. "
        "Please reopen EzCursor; details are in ezcursor.log.",
    "+ Hồ sơ riêng": "+ Own profile", "✓ Hồ sơ riêng": "✓ Own profile", "Hồ sơ: ": "Profile: ",
    "Xóa hồ sơ riêng \"{n}\"? Game này sẽ dùng lại kiểu Mặc định.":
        "Delete the profile \"{n}\"? This game will go back to the Default style.",
}


def T(text):
    """Dịch chuỗi giao diện sang ngôn ngữ đang chọn (mặc định tiếng Việt)."""
    if LANG == "en":
        return TR_EN.get(text, text)
    return text

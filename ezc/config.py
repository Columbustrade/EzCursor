"""Cấu hình: giá trị mặc định, đọc / ghi config.json, hồ sơ từng game, kho trực tuyến."""

import collections.abc
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from . import i18n
from .base import APP_DIR, APP_VERSION, CONFIG_PATH, MY_DIR, MY_EXTS, OLD_DIR, log
from .startup import run_value_exists, set_startup
from .i18n import LANGUAGES
from .hotkeys import HOTKEY_ACTIONS, HOTKEY_MODS, HOTKEY_VKS


OMBRE_SPEEDS = {"slow": 150, "mid": 90, "fast": 50}      # ms mỗi khung (24 khung một vòng)

TRANSPARENT = "#010101"
SHAPES = ["EzDrop", "EzPink", "ez_crosshair", "ez_sword", "ez_crystal", "ez_gem", "ez_rune", "ez_orb", "ez_flame", "ez_spear", "ez_feather", "ez_star", "ez_shot", "ez_neon", "Mũi tên", "Vòng tròn", "Dấu thập", "Chấm tròn", "Kim cương", "Ảnh tải lên", "Bibata"]
HOTSPOTS = ["Giữa ảnh", "Góc trên trái", "Theo file"]
ARROW_TIP = 3

DEFAULT_CFG = {
    "color": "#ff2828",
    "shape": "EzDrop",
    "size": 64,
    "image": "",
    "hotspot": HOTSPOTS[0],
    "tint_image": True,
    "glow": True,
    "cursor_sparkle": False,
    "splash": True,
    "fx_trail": "off",
    "fx_click": "off",
    "fx_color": "cursor",
    "fx_density": "mid",
    "bibata_cursor": "left_ptr",
    "bibata_theme": "amber",
    "bibata_style": "modern",
    "bibata_hand": "right",
    "own_theme": "original",
    "hold_left": False,
    "hold_left_color": "#22D3EE",
    "hold_right": False,
    "hold_right_color": "#FFD60A",
    "ombre": False,                                     # dải màu ombre thay cho một màu
    "ombre_colors": ["#FF2E93", "#FF8A3D", "#FFD60A"],
    "ombre_anim": False,                                # dải màu chạy chầm chậm
    "ombre_speed": "mid",
    "hide_real": True,
    "enabled": True,
    "all_apps": False,
    "apps": [],
    "tray_hint_shown": False,
    "auto_check_update": True,
    "last_update_check": 0,
    "skipped_version": "",
    "language": "vi",
    "dpi_scale": False,
    "find_shake": True,
    "catalog_got": {},        # con trỏ đã tải từ kho trực tuyến: {id: tên file trong my_cursors}
    "made_cursors": {},       # con trỏ tự tạo: {tên file trong my_cursors: thông số} để mở lại sửa
    "sys_skip": [],            # game tự đặt con trỏ riêng -> dùng Lớp phủ dù đang ở chế độ Con trỏ thật
    "cursor_mode": "overlay",  # "overlay" (lớp phủ, nhiều hiệu ứng) / "system" (con trỏ thật, không độ trễ)
    "predict": True,           # đoán trước vị trí con trỏ theo tốc độ chuột (bù ~nửa khung hình)
    "keep_taskbar": True,      # rê chuột xuống taskbar vẫn dùng con trỏ EzCursor
    "stream": False,           # chế độ stream: trang cục bộ cho nguồn Browser của OBS
    "stream_port": 47391,      # cổng của trang đó (bận thì dùng cổng kế tiếp và lưu lại)
    "setup_done": False,      # đã qua màn hình thiết lập lần đầu
    "favorites": [],          # con trỏ yêu thích: mã hình, "bib:<tên>" hoặc "my:<tên file>"
    "profiles": [],      # hồ sơ riêng: [{"name": ..., "exes": [...], "style": {...}}]
    "hotkeys": {
        "toggle": {"mods": ["ctrl", "alt"], "vk": 0x48},   # H
        "shape": {"mods": ["ctrl", "alt"], "vk": 0x52},    # R
        "quit": {"mods": ["ctrl", "alt"], "vk": 0x51},     # Q
        "find": {"mods": ["ctrl", "alt"], "vk": 0x46},     # F
        "color": {"mods": ["ctrl", "alt"]},                # + phím số 1..5
    },
}

# Game ARPG phổ biến: (tên hiển thị, các file chạy có thể gặp)
ARPG_GAMES = [
    ("Last Epoch", ["Last Epoch.exe"]),
    ("Path of Exile 1 / 2", ["PathOfExile.exe", "PathOfExileSteam.exe", "PathOfExile_x64.exe",
                             "PathOfExile_x64Steam.exe"]),
    ("Diablo IV", ["Diablo IV.exe"]),
    ("Diablo III", ["Diablo III64.exe", "Diablo III.exe"]),
    ("Diablo II: Resurrected", ["D2R.exe"]),
    ("Grim Dawn", ["Grim Dawn.exe"]),
    ("Torchlight II", ["Torchlight2.exe"]),
    ("Titan Quest", ["TQ.exe"]),
    ("Lost Ark", ["LOSTARK.exe"]),
]


def migrate_old_version():
    """Chuyển cài đặt từ bản 'Con Trỏ Màu' cũ sang EzCursor (chỉ làm 1 lần)."""
    if CONFIG_PATH.exists() or not (OLD_DIR / "config.json").exists():
        return
    for f in OLD_DIR.iterdir():
        if f.is_file() and f.name != "show.flag":
            try:
                shutil.copy2(f, APP_DIR / f.name)
            except OSError:
                pass
    try:
        old = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if "game_only" in old:
            old["all_apps"] = not old["game_only"]
        CONFIG_PATH.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    if run_value_exists("ConTroMau"):     # chuyển luôn chế độ khởi động cùng Windows
        try:
            set_startup(False, "ConTroMau")
            set_startup(True)
        except OSError:
            pass


def default_cfg():
    return json.loads(json.dumps(DEFAULT_CFG))     # bản sao sâu


# Các cài đặt thuộc về "kiểu con trỏ": mỗi hồ sơ game có một bộ riêng
STYLE_KEYS = ("color", "shape", "size", "image", "hotspot", "tint_image", "glow", "cursor_sparkle",
              "fx_trail", "fx_click", "fx_color", "fx_density",
              "bibata_cursor", "bibata_theme", "bibata_style", "bibata_hand", "own_theme",
              "hold_left", "hold_left_color", "hold_right", "hold_right_color",
              "ombre", "ombre_colors", "ombre_anim", "ombre_speed")


def clean_style(cfg):
    """Sửa các giá trị kiểu con trỏ không hợp lệ (dùng cho cấu hình chính lẫn từng hồ sơ)."""
    for k in STYLE_KEYS:
        if k not in cfg:
            cfg[k] = DEFAULT_CFG[k]
    if cfg["shape"] not in SHAPES:
        cfg["shape"] = DEFAULT_CFG["shape"]
    if cfg["hotspot"] not in HOTSPOTS:
        cfg["hotspot"] = HOTSPOTS[0]
    cfg["size"] = max(24, min(160, int(cfg["size"])))
    if cfg["bibata_theme"] not in ("amber", "classic", "ice", "custom"):
        cfg["bibata_theme"] = "amber"
    if cfg["own_theme"] not in ("original", "custom"):
        cfg["own_theme"] = "original"
    if cfg["bibata_style"] not in ("modern", "original"):
        cfg["bibata_style"] = "modern"
    if cfg["bibata_hand"] not in ("right", "left"):
        cfg["bibata_hand"] = "right"
    if cfg["fx_trail"] not in ("off", "sparkle", "neon", "rainbow", "ghost", "bubble"):
        cfg["fx_trail"] = "off"
    if cfg["fx_click"] not in ("off", "ripple", "burst"):
        cfg["fx_click"] = "off"
    if cfg["fx_color"] not in ("cursor", "ez"):
        cfg["fx_color"] = "cursor"
    if cfg["fx_density"] not in ("low", "mid", "high"):
        cfg["fx_density"] = "mid"
    for k in ("color", "hold_left_color", "hold_right_color"):
        if not isinstance(cfg[k], str) or len(cfg[k]) != 7 or not cfg[k].startswith("#"):
            cfg[k] = DEFAULT_CFG[k]
    for k in ("tint_image", "glow", "cursor_sparkle", "hold_left", "hold_right", "ombre", "ombre_anim"):
        cfg[k] = bool(cfg[k])
    oc = cfg["ombre_colors"]
    oc = [x for x in oc if isinstance(x, str) and len(x) == 7 and x.startswith("#")] if isinstance(oc, list) else []
    cfg["ombre_colors"] = oc[:5] if len(oc) >= 2 else list(DEFAULT_CFG["ombre_colors"])
    if cfg["ombre_speed"] not in OMBRE_SPEEDS:
        cfg["ombre_speed"] = "mid"
    if cfg["image"] and not Path(cfg["image"]).exists():
        name = Path(cfg["image"]).name
        alt = next((d / name for d in (MY_DIR, APP_DIR) if (d / name).exists()), None)
        cfg["image"] = str(alt) if alt else ""
    if cfg["shape"] == "Ảnh tải lên" and not cfg["image"]:     # file ảnh đã mất: quay về con trỏ mặc định
        cfg["shape"] = DEFAULT_CFG["shape"]
    return cfg


# Kho con trỏ trực tuyến (2.0): danh sách nằm trên website, thêm con trỏ mới không cần phát hành app
CATALOG_URL = "https://ezcursor.github.io/catalog/catalog.json"
CAT_DIR = APP_DIR / "catalog"            # bộ nhớ đệm: danh sách + ảnh nhỏ
CAT_EXTS = {".cur", ".ani", ".png", ".gif"}
CAT_MAX = 3 * 1024 * 1024


def http_get(url, limit):
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise ValueError("URL không hợp lệ")
    req = urllib.request.Request(url, headers={"User-Agent": f"EzCursor/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=12) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File quá lớn")
    return data


def clean_catalog(data):
    """Chỉ giữ các mục hợp lệ của catalog.json (tên file đơn giản, đúng định dạng, có mã kiểm tra)."""
    out = []
    for e in data.get("cursors", []) if isinstance(data, dict) else []:
        try:
            cid, f, th = e["id"], e["file"], e["thumb"]
            ok = (re.fullmatch(r"[a-z0-9_-]{1,40}", cid) and re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", f)
                  and re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", th) and ".." not in f + th
                  and Path(f).suffix.lower() in CAT_EXTS and th.lower().endswith(".png")
                  and re.fullmatch(r"[0-9a-f]{64}", e["sha256"]) and 0 < int(e["size"]) <= CAT_MAX)
            if not ok:
                continue
            name = e.get("name")
            name = name if isinstance(name, dict) else {"vi": str(name or cid)}
            out.append({"id": cid, "file": f, "thumb": th, "sha256": e["sha256"], "size": int(e["size"]),
                        "name": {k: str(v)[:40] for k, v in name.items()}, "added": str(e.get("added", ""))[:10]})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def catalog_name(e):
    return e["name"].get(i18n.LANG) or e["name"].get("vi") or next(iter(e["name"].values()), e["id"])


def my_cursor_files():
    """Các con trỏ người dùng đã thêm, mới nhất ở cuối."""
    try:
        files = [f for f in MY_DIR.iterdir() if f.is_file() and f.suffix.lower() in MY_EXTS]
    except OSError:
        return []
    return sorted(files, key=lambda f: f.stat().st_mtime)


def unique_my_path(name):
    stem = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in Path(name).stem).strip() or "cursor"
    ext = Path(name).suffix.lower()
    dest, i = MY_DIR / f"{stem}{ext}", 2
    while dest.exists():
        dest, i = MY_DIR / f"{stem}-{i}{ext}", i + 1
    return dest


def migrate_my_cursors(cfg):
    """Đưa ảnh tải lên ở các bản trước (custom*.*) vào "Con trỏ của bạn" và sửa đường dẫn trong cài đặt."""
    try:
        MY_DIR.mkdir(parents=True, exist_ok=True)
        moved = {}
        for f in APP_DIR.glob("custom*.*"):
            if f.is_file() and f.suffix.lower() in MY_EXTS:
                dest = unique_my_path(f.name)
                shutil.move(str(f), str(dest))
                moved[f.name.lower()] = str(dest)
        if not moved:
            return
        styles = [cfg] + [pr.get("style", {}) for pr in cfg.get("profiles", []) if isinstance(pr, dict)]
        for st in styles:
            img = st.get("image") or ""
            if img and Path(img).name.lower() in moved:
                st["image"] = moved[Path(img).name.lower()]
    except Exception:
        pass


def write_cfg(data):
    """Ghi config.json an toàn: ghi ra file tạm rồi thay thế, mất điện giữa chừng cũng không hỏng file cũ."""
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def load_cfg():
    cfg = default_cfg()
    raw = {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cfg.update(raw)
    except FileNotFoundError:
        pass
    except Exception as e:      # file hỏng: giữ lại bản hỏng để còn cứu, rồi dùng cài đặt mặc định
        raw = {}
        try:
            CONFIG_PATH.replace(CONFIG_PATH.with_name("config.broken.json"))
        except OSError:
            pass
        log.warning("config.json bị hỏng (%s), đã lưu bản hỏng thành config.broken.json và dùng cài đặt mặc định", e)
    if not isinstance(raw, dict) or "setup_done" not in raw:     # đã dùng bản cũ thì không cần thiết lập lại
        cfg["setup_done"] = bool(raw)
    try:
        clean_style(cfg)
    except Exception:
        for k in STYLE_KEYS:
            cfg[k] = DEFAULT_CFG[k]
    profiles = []
    for pr in cfg.get("profiles") if isinstance(cfg.get("profiles"), list) else []:
        try:
            exes = [e for e in pr["exes"] if isinstance(e, str) and e]
            if not exes or not isinstance(pr.get("name"), str):
                continue
            st = {k: cfg[k] for k in STYLE_KEYS}
            st.update({k: v for k, v in pr.get("style", {}).items() if k in STYLE_KEYS})
            profiles.append({"name": pr["name"], "exes": exes, "style": clean_style(st)})
        except Exception:
            continue
    cfg["profiles"] = profiles
    cfg["dpi_scale"] = bool(cfg.get("dpi_scale"))
    cfg["find_shake"] = bool(cfg.get("find_shake", True))
    sk = cfg.get("sys_skip") if isinstance(cfg.get("sys_skip"), list) else []
    cfg["sys_skip"] = [x for x in sk if isinstance(x, str)][:50]
    cfg["keep_taskbar"] = bool(cfg.get("keep_taskbar", True))
    cfg["predict"] = bool(cfg.get("predict", True))
    cfg["stream"] = cfg.get("stream") is True
    port = cfg.get("stream_port")
    # tối đa 65526: chế độ stream còn thử thêm 9 cổng kế tiếp khi cổng bận
    if not (isinstance(port, int) and not isinstance(port, bool) and 1024 <= port <= 65526):
        cfg["stream_port"] = DEFAULT_CFG["stream_port"]
    if cfg.get("cursor_mode") not in ("overlay", "system"):
        cfg["cursor_mode"] = "overlay"
    made = cfg.get("made_cursors") if isinstance(cfg.get("made_cursors"), dict) else {}
    cfg["made_cursors"] = {k: v for k, v in made.items() if isinstance(k, str) and isinstance(v, dict)}
    got = cfg.get("catalog_got") if isinstance(cfg.get("catalog_got"), dict) else {}
    # file đã bị xoá khỏi my_cursors thì coi như chưa tải, để kho trực tuyến cho tải lại
    cfg["catalog_got"] = {k: v for k, v in got.items() if isinstance(k, str) and isinstance(v, str)
                          and v and Path(v).name == v and (MY_DIR / v).is_file()}
    favs = cfg.get("favorites") if isinstance(cfg.get("favorites"), list) else []
    cfg["favorites"] = list(dict.fromkeys(f for f in favs if isinstance(f, str) and f))[:60]
    migrate_my_cursors(cfg)
    cfg["hotkeys"] = clean_hotkeys(cfg.get("hotkeys"))
    if cfg["language"] not in dict(LANGUAGES):
        cfg["language"] = "vi"
    if not isinstance(cfg["apps"], list):
        cfg["apps"] = list(DEFAULT_CFG["apps"])
    return cfg


class ProfileCfg(collections.abc.MutableMapping):
    """Cấu hình dùng trong app: các khóa kiểu con trỏ đọc/ghi vào hồ sơ đang chọn (target),
    các khóa còn lại đọc/ghi vào cấu hình chính (base). Hồ sơ Mặc định chính là base."""

    def __init__(self, base):
        self.base = base
        self.target = base

    def __getitem__(self, k):
        if k in STYLE_KEYS and self.target is not self.base:
            return self.target.get(k, self.base[k])
        return self.base[k]

    def __setitem__(self, k, v):
        (self.target if k in STYLE_KEYS else self.base)[k] = v

    def __delitem__(self, k):
        del self.base[k]

    def __iter__(self):
        return iter(self.base)

    def __len__(self):
        return len(self.base)


def clean_hotkeys(hk):
    """Kiểm tra phím tắt đọc từ file cài đặt; mục nào hỏng thì dùng mặc định."""
    out = json.loads(json.dumps(DEFAULT_CFG["hotkeys"]))
    if not isinstance(hk, dict):
        return out
    names = {m for m, _, _ in HOTKEY_MODS}
    for act in HOTKEY_ACTIONS:
        b = hk.get(act)
        if not isinstance(b, dict):
            continue
        mods = [m for m in b.get("mods", []) if m in names] if isinstance(b.get("mods"), list) else []
        if not ({"ctrl", "alt"} & set(mods)):
            continue
        if act == "color":
            out[act] = {"mods": mods}
        elif isinstance(b.get("vk"), int) and b["vk"] in HOTKEY_VKS:
            out[act] = {"mods": mods, "vk": b["vk"]}
    return out

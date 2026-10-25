/* EzCursor – trang giới thiệu: đổi ngôn ngữ, lấy bản phát hành mới nhất, cảnh thử con trỏ, ủng hộ. */
(function () {
  "use strict";

  var REPO = "Columbustrade/EzCursor";
  var CFG = window.EZ_CONFIG || {};
  // Mở file trên máy (hoặc localhost) thì hiện các ô còn trống để biết cần điền gì.
  var DEV = location.protocol === "file:" || /^(localhost|127\.)/.test(location.hostname);

  // ------------------------------------------------------------------ Bản dịch tiếng Anh
  var EN = {
    "skip": "Skip to content",
    "nav.about": "About", "nav.shots": "Screenshots", "nav.guide": "Guide", "nav.support": "Support",
    "hero.title": "See your cursor in every fight.",
    "hero.lead": "EzCursor draws a big, bright cursor over Windows games with a hard-to-see one, like Last Epoch. Free and open source.",
    "hero.download": "Download free for Windows",
    "hero.os": "Windows 10 / 11",
    "hero.toggle": "EzCursor is on",
    "hero.toggleOff": "EzCursor is off",
    "hero.hint": "Move and click inside this area to try it. Turn it off to see how easy the default cursor is to lose.",
    "about.title": "Born from losing the cursor in Last Epoch",
    "about.p1": "In many ARPGs the cursor is small, dark and easily lost among spell effects, monsters and the map. Losing it for a second is enough to click the wrong spot.",
    "about.p2": "EzCursor fixes that by drawing its own large, high-contrast cursor right on top of the game. Leave the game or open Start or Alt+Tab, and the normal Windows cursor comes back.",
    "about.f1t": "Doesn't touch the game",
    "about.f1d": "EzCursor is a transparent overlay running outside the game. It only reads the mouse position and never modifies game files or memory.",
    "about.f2t": "Only in the games you pick",
    "about.f2d": "Pick games by their executable name. Every other app stays exactly as it is.",
    "about.f3t": "Free and open source",
    "about.f3d": "Released under the GPL-3.0 license, with the full source code on GitHub.",
    "shots.title": "The app",
    "shots.ingame": "In game",
    "tab.cursor": "Cursor", "tab.library": "Library", "tab.fx": "Effects", "tab.apps": "Apps", "tab.opts": "Options",
    "feat.title": "What's inside",
    "feat.1t": "15 ready-made cursors",
    "feat.1d": "Liquid Drop, Pink Shard and 13 Bibata cursors in Amber, Classic, Ice or a custom color, including left-handed versions.",
    "feat.2t": "Or make your own",
    "feat.2d": "Pick a shape, color and size from 24 to 160 px, add a glow, or use your own PNG image.",
    "feat.3t": "Effects",
    "feat.3d": "Sparkle, neon, rainbow, ghost and bubble trails; ripple or fireworks on click.",
    "feat.4t": "Steps aside when needed",
    "feat.4d": "The real cursor returns when you open Start, Search, Alt+Tab or hover the taskbar.",
    "feat.5t": "Light and out of the way",
    "feat.5d": "Lives in the system tray, can start with Windows and checks for updates on its own.",
    "feat.6t": "Vietnamese and English",
    "feat.6d": "Switch language in the Options tab, no restart needed.",
    "guide.title": "Get started in 4 steps",
    "guide.1t": "Download and install",
    "guide.1d": "Run the <code>EzCursor_Setup</code> file you downloaded. If Windows shows <em>“Windows protected your PC”</em>, click <b>More info</b> and then <b>Run anyway</b>. No admin rights needed.",
    "guide.2t": "Use windowed mode",
    "guide.2d": "In the game's graphics settings, choose <b>Borderless</b> or <b>Windowed</b>. EzCursor can't draw over exclusive fullscreen.",
    "guide.3t": "Pick your game",
    "guide.3d": "Start the game, then open EzCursor. In the <b>Apps</b> tab, click <b>Refresh</b>, tick the game and click <b>Apply</b>.",
    "guide.4t": "Choose a cursor you like",
    "guide.4d": "Adjust it in the <b>Cursor</b> or <b>Library</b> tab and add a trail in <b>Effects</b>. Click X to tuck EzCursor into the system tray.",
    "keys.title": "Hotkeys",
    "keys.h": "Turn the cursor on / off", "keys.r": "Change shape", "keys.c": "Change color", "keys.q": "Quit EzCursor",
    "faq.title": "Questions",
    "faq.1q": "Can using EzCursor get my game account banned?",
    "faq.1a": "EzCursor doesn't modify files or read or write game memory; it only draws a transparent window on top of the screen. Every game has its own terms, though. Check them yourself, and avoid competitive games with strict anti-cheat.",
    "faq.2q": "I installed it but don't see the new cursor in game",
    "faq.2a": "Check three things: the game runs in Borderless or Windowed; the game is ticked and applied in the Apps tab; EzCursor is on (Ctrl + Alt + H). The Status panel on the left of the app shows which game EzCursor is waiting for.",
    "faq.3q": "My mouse cursor disappeared",
    "faq.3a": "Open EzCursor again and quit with Ctrl + Alt + Q to bring the Windows cursor back. If that doesn't help, sign out or restart Windows.",
    "faq.4q": "Do the effects slow my game down?",
    "faq.4a": "Effects are only drawn while particles are on screen. On a slower PC, or if you notice stutter, set Density to Low or turn effects off in the Effects tab.",
    "faq.5q": "How do I uninstall it?",
    "faq.5a": "Go to Settings → Apps → Installed apps, select EzCursor and click Uninstall. Saved settings are removed too.",
    "support.title": "Support EzCursor",
    "support.lead": "EzCursor is free and will stay free. If it makes your games more comfortable, a coffee helps me find time for new features.",
    "support.bank": "Bank transfer",
    "support.paypal": "For supporters outside Vietnam.",
    "support.alt": "Can't donate? Starring the <a href=\"https://github.com/Columbustrade/EzCursor\" target=\"_blank\" rel=\"noopener\">GitHub repo</a> or telling a friend about EzCursor helps too.",
    "foot.license": "Released under the <a href=\"https://github.com/Columbustrade/EzCursor/blob/main/LICENSE\" target=\"_blank\" rel=\"noopener\">GPL-3.0</a> license. Bibata cursors by <a href=\"https://github.com/ful1e5/Bibata_Cursor\" target=\"_blank\" rel=\"noopener\">Abdulkaiz Khatri</a>, GPL-3.0.",
    "foot.releases": "All versions", "foot.issues": "Report a bug"
  };

  // Chuỗi dùng trong JS (không nằm sẵn trong HTML)
  var STR = {
    vi: {
      title: "EzCursor – Con trỏ chuột dễ nhìn cho game",
      latest: "Phiên bản mới nhất", version: "Phiên bản ", toggleOff: "EzCursor đang tắt",
      copy: "Sao chép", copied: "Đã sao chép", phone: "Số điện thoại", holder: "Chủ tài khoản",
      account: "Số tài khoản", bank: "Ngân hàng", paypalBtn: "Ủng hộ qua PayPal",
      pending: "Chưa điền thông tin. Mở file config.js để thêm.",
      missingShot: "Chưa có ảnh. Thêm file vào", shotAlt: "Tab {t} của EzCursor",
      caps: {
        cursor: "Chọn hình dạng, màu và kích thước, xem trước trực tiếp.",
        library: "Liquid Drop, Mảnh hồng và 13 con trỏ Bibata, có chủ đề màu và bản cho tay trái.",
        fx: "Vệt theo con trỏ, hiệu ứng khi click và nút thử ngay trên màn hình.",
        apps: "Tích những game sẽ dùng con trỏ của EzCursor rồi bấm Áp dụng.",
        opts: "Ngôn ngữ, khởi động cùng Windows, cập nhật và phím tắt."
      }
    },
    en: {
      title: "EzCursor – An easy-to-see cursor for games",
      latest: "Latest version", version: "Version ", toggleOff: "EzCursor is off",
      copy: "Copy", copied: "Copied", phone: "Phone", holder: "Account holder",
      account: "Account number", bank: "Bank", paypalBtn: "Support via PayPal",
      pending: "Not filled in yet. Edit config.js to add it.",
      missingShot: "No image yet. Add the file", shotAlt: "EzCursor {t} tab",
      caps: {
        cursor: "Pick a shape, color and size with a live preview.",
        library: "Liquid Drop, Pink Shard and 13 Bibata cursors, with color themes and left-handed versions.",
        fx: "Cursor trails, click effects and a button to try them on screen.",
        apps: "Tick the games that should use the EzCursor cursor, then click Apply.",
        opts: "Language, start with Windows, updates and hotkeys."
      }
    }
  };

  var lang = "vi";
  var release = null;
  var VI = {};   // tiếng Việt gốc lấy từ HTML

  function $(s, root) { return (root || document).querySelector(s); }
  function $$(s, root) { return Array.prototype.slice.call((root || document).querySelectorAll(s)); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }

  $$("[data-i18n]").forEach(function (el) { VI[el.dataset.i18n] = el.textContent; });
  $$("[data-i18n-html]").forEach(function (el) { VI[el.dataset.i18nHtml] = el.innerHTML; });

  function setLang(l) {
    lang = l === "en" ? "en" : "vi";
    document.documentElement.lang = lang;
    document.title = STR[lang].title;
    $$("[data-i18n]").forEach(function (el) {
      var k = el.dataset.i18n;
      el.textContent = lang === "en" && EN[k] ? EN[k] : VI[k];
    });
    $$("[data-i18n-html]").forEach(function (el) {
      var k = el.dataset.i18nHtml;
      el.innerHTML = lang === "en" && EN[k] ? EN[k] : VI[k];
    });
    $$(".lang button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.lang === lang)); });
    store("ez-lang", lang);
    updateToggleLabel();
    showShot(currentShot);
    renderRelease();
    renderSupport();
    renderGameShots();
  }

  $$(".lang button").forEach(function (b) { b.addEventListener("click", function () { setLang(b.dataset.lang); }); });

  // ------------------------------------------------------------------ Ảnh giao diện theo tab
  var currentShot = "cursor";
  var tabs = $$(".tabs [role=tab]");
  function showShot(key) {
    currentShot = key;
    tabs.forEach(function (t) {
      var on = t.dataset.shot === key;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });
    var img = $("#shot-img");
    var label = (tabs.filter(function (t) { return t.dataset.shot === key; })[0] || {}).textContent || key;
    img.src = "images/app-" + key + "-" + lang + ".webp";
    img.alt = STR[lang].shotAlt.replace("{t}", label);
    $("#shot-cap").textContent = STR[lang].caps[key];
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { showShot(t.dataset.shot); });
    t.addEventListener("keydown", function (e) {
      var d = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (!d) return;
      e.preventDefault();
      var n = tabs[(i + d + tabs.length) % tabs.length];
      n.focus(); showShot(n.dataset.shot);
    });
  });
  // Tải trước ảnh các tab để bấm là hiện ngay
  window.addEventListener("load", function () {
    ["vi", "en"].forEach(function (l) {
      tabs.forEach(function (t) { new Image().src = "images/app-" + t.dataset.shot + "-" + l + ".webp"; });
    });
  });

  // ------------------------------------------------------------------ Bản phát hành mới nhất
  function renderRelease() {
    var ver = $("[data-ver]"), size = $("[data-size]");
    if (!release) { ver.textContent = STR[lang].latest; return; }
    ver.textContent = STR[lang].version + release.version;
    size.textContent = release.size ? (release.size / 1048576).toFixed(1) + " MB" : "";
  }
  fetch("https://api.github.com/repos/" + REPO + "/releases/latest", { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
    .then(function (d) {
      var asset = (d.assets || []).filter(function (a) { return /\.exe$/i.test(a.name); })[0];
      release = { version: String(d.tag_name || "").replace(/^v/i, ""), size: asset ? asset.size : 0 };
      if (asset) $$("[data-download]").forEach(function (a) { a.href = asset.browser_download_url; });
      renderRelease();
    })
    .catch(function () { /* giữ liên kết tới trang Releases */ });

  // ------------------------------------------------------------------ Ảnh trong game
  function renderGameShots() {
    var box = $("#trong-game"), grid = $(".ingame-grid", box);
    var list = CFG.gameShots || [];
    grid.innerHTML = "";
    var shown = 0;
    list.forEach(function (s) {
      var fig = document.createElement("figure");
      var img = new Image();
      img.decoding = "async";
      img.alt = s[lang] || s.vi || "";
      img.onload = function () { fig.hidden = false; box.hidden = false; };
      img.onerror = function () {
        if (!DEV) { fig.remove(); return; }
        fig.innerHTML = "";
        var m = document.createElement("div");
        m.className = "missing";
        m.innerHTML = "<div>" + STR[lang].missingShot + "<br><code></code></div>";
        $("code", m).textContent = "docs/" + s.src;
        fig.appendChild(m);
        fig.hidden = false; box.hidden = false;
      };
      fig.hidden = true;
      fig.appendChild(img);
      if (s[lang] || s.vi) {
        var cap = document.createElement("figcaption");
        cap.textContent = s[lang] || s.vi;
        fig.appendChild(cap);
      }
      grid.appendChild(fig);
      img.src = s.src;
      shown++;
    });
    if (!shown) box.hidden = true;
  }

  // ------------------------------------------------------------------ Ủng hộ
  function toast(msg) {
    var t = $(".toast");
    t.textContent = msg; t.classList.add("show");
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.classList.remove("show"); }, 1600);
  }
  function row(label, value, copyable) {
    var r = document.createElement("div"); r.className = "row";
    var l = document.createElement("span"); l.className = "label"; l.textContent = label + ":";
    var v = document.createElement("span"); v.className = "val"; v.textContent = value;
    r.appendChild(l); r.appendChild(v);
    if (copyable) {
      var b = document.createElement("button"); b.type = "button"; b.className = "copy"; b.textContent = STR[lang].copy;
      b.addEventListener("click", function () {
        var done = function () { toast(STR[lang].copied); };
        if (navigator.clipboard) navigator.clipboard.writeText(value.replace(/\s/g, "")).then(done, done);
      });
      r.appendChild(b);
    }
    return r;
  }
  function qrImg(src, alt) {
    var i = new Image(); i.src = src; i.alt = alt; i.loading = "lazy"; i.width = 240; i.height = 240; return i;
  }
  function renderSupport() {
    var s = STR[lang];
    var any = false;
    $$(".method").forEach(function (card) {
      var kind = card.dataset.method, c = CFG[kind] || {};
      var qr = $(".qr", card), acct = $(".acct", card);
      if (qr) qr.innerHTML = "";
      acct.innerHTML = "";
      var filled = false;
      if (kind === "momo") {
        if (c.qr) { qr.appendChild(qrImg(c.qr, "QR MoMo")); filled = true; }
        if (c.phone) { acct.appendChild(row(s.phone, c.phone, true)); filled = true; }
        if (c.name) acct.appendChild(row(s.holder, c.name));
      } else if (kind === "bank") {
        if (c.qr) { qr.appendChild(qrImg(c.qr, "QR " + (c.bank || ""))); filled = true; }
        if (c.bank) acct.appendChild(row(s.bank, c.bank));
        if (c.account) { acct.appendChild(row(s.account, c.account, true)); filled = true; }
        if (c.name) acct.appendChild(row(s.holder, c.name));
      } else if (kind === "paypal" && c.url) {
        var a = document.createElement("a");
        a.className = "btn btn-paypal"; a.href = c.url; a.target = "_blank"; a.rel = "noopener";
        a.textContent = s.paypalBtn;
        acct.appendChild(a); filled = true;
      }
      if (!filled && DEV) {
        var p = document.createElement("p"); p.className = "pending"; p.textContent = s.pending;
        acct.appendChild(p);
      }
      card.hidden = !filled && !DEV;
      any = any || filled;
    });
    $(".methods").hidden = !any && !DEV;
  }

  // ------------------------------------------------------------------ Cảnh thử con trỏ (hero)
  var hero = $(".hero"), canvas = $(".hero-scene"), ctx = canvas.getContext("2d");
  var toggle = $("#demo-on");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var W = 0, H = 0, DPR = 1, embers = [], blobs = [], parts = [], rings = [], running = false, visible = true;
  var COLORS = ["#2EE59D", "#2F80FF", "#FF2E93", "#FFFFFF"];

  function updateToggleLabel() {
    var span = toggle.parentNode.querySelector("[data-i18n]");
    span.textContent = toggle.checked ? (lang === "en" ? EN["hero.toggle"] : VI["hero.toggle"]) : STR[lang].toggleOff;
  }
  function applyToggle() {
    hero.classList.toggle("ez-on", toggle.checked && finePointer);
    updateToggleLabel();
  }
  toggle.addEventListener("change", applyToggle);

  function resize() {
    DPR = Math.min(2, window.devicePixelRatio || 1);
    W = hero.clientWidth; H = hero.clientHeight;
    canvas.width = W * DPR; canvas.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    // vài vùng "phép thuật" mờ và tàn lửa trôi, giống nền một trận đánh ARPG
    blobs = [
      { x: 0.72, y: 0.36, r: 0.30, c: "rgba(140,70,255,", a: 0.20, s: 0.00031 },
      { x: 0.86, y: 0.78, r: 0.24, c: "rgba(255,120,40,", a: 0.16, s: 0.00042 },
      { x: 0.52, y: 0.88, r: 0.20, c: "rgba(255,46,147,", a: 0.10, s: 0.00027 },
      { x: 0.95, y: 0.12, r: 0.18, c: "rgba(47,128,255,", a: 0.14, s: 0.00036 }
    ];
    var n = Math.round((W * H) / 9000);
    embers = [];
    for (var i = 0; i < n; i++) embers.push(newEmber(true));
    if (!running) draw(performance.now());
  }
  function newEmber(anyY) {
    var warm = Math.random() < 0.7;
    return {
      x: Math.random() * W, y: anyY ? Math.random() * H : H + 10,
      vy: -(8 + Math.random() * 26), vx: (Math.random() - 0.5) * 10,
      r: 0.6 + Math.random() * 1.8, life: Math.random() * 6,
      c: warm ? (Math.random() < 0.5 ? "255,150,60" : "255,90,60") : "150,120,255"
    };
  }

  function star(x, y, r, color, alpha) {
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, y - r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.quadraticCurveTo(x, y, x, y + r);
    ctx.quadraticCurveTo(x, y, x - r, y);
    ctx.quadraticCurveTo(x, y, x, y - r);
    ctx.fill();
  }

  var last = 0;
  function draw(now) {
    var dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    ctx.clearRect(0, 0, W, H);
    // vùng sáng mờ
    blobs.forEach(function (b, i) {
      var k = reduce ? 0 : Math.sin(now * b.s + i);
      var x = b.x * W + k * 30, y = b.y * H + Math.cos(now * b.s + i) * 20;
      var R = b.r * Math.max(W, H);
      var g = ctx.createRadialGradient(x, y, 0, x, y, R);
      g.addColorStop(0, b.c + (b.a * (0.85 + 0.15 * k)) + ")");
      g.addColorStop(1, b.c + "0)");
      ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    });
    // tàn lửa
    for (var i = 0; i < embers.length; i++) {
      var e = embers[i];
      if (!reduce) { e.y += e.vy * dt; e.x += e.vx * dt + Math.sin(now / 900 + i) * 0.15; e.life += dt; }
      if (e.y < -10) embers[i] = e = newEmber(false);
      var tw = 0.45 + 0.55 * Math.abs(Math.sin(e.life * 2.2));
      ctx.globalAlpha = tw * 0.8;
      ctx.fillStyle = "rgb(" + e.c + ")";
      ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, 6.283); ctx.fill();
    }
    // vệt lấp lánh theo con trỏ
    for (var j = parts.length - 1; j >= 0; j--) {
      var p = parts[j];
      p.t += dt;
      if (p.t > p.life) { parts.splice(j, 1); continue; }
      var f = 1 - p.t / p.life;
      p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 30 * dt;
      star(p.x, p.y, p.r * (0.4 + 0.6 * f), p.c, f);
    }
    // gợn sóng khi click
    for (var k = rings.length - 1; k >= 0; k--) {
      var g2 = rings[k];
      g2.t += dt;
      if (g2.t > 0.6) { rings.splice(k, 1); continue; }
      var q = g2.t / 0.6;
      ctx.globalAlpha = 1 - q;
      ctx.lineWidth = 3 * (1 - q) + 1;
      ctx.strokeStyle = COLORS[g2.i % 3];
      ctx.beginPath(); ctx.arc(g2.x, g2.y, 8 + q * 56, 0, 6.283); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    running = visible && !document.hidden && (!reduce || parts.length || rings.length);
    if (running) requestAnimationFrame(draw);
  }
  function kick() { if (!running) { running = true; last = 0; requestAnimationFrame(draw); } }

  var lastSpawn = 0, px = -1, py = -1;
  hero.addEventListener("pointermove", function (e) {
    if (!toggle.checked || e.pointerType !== "mouse") return;
    var r = hero.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    var dist = px < 0 ? 0 : Math.hypot(x - px, y - py);
    px = x; py = y;
    var now = performance.now();
    if (now - lastSpawn < (reduce ? 120 : 16) || parts.length > 160) return;
    lastSpawn = now;
    var n = reduce ? 1 : Math.min(3, 1 + Math.floor(dist / 18));
    for (var i = 0; i < n; i++) {
      parts.push({
        x: x + 6 + (Math.random() - 0.5) * 10, y: y + 8 + (Math.random() - 0.5) * 10,
        vx: (Math.random() - 0.5) * 30, vy: (Math.random() - 0.5) * 30,
        r: 5 + Math.random() * 7, life: 0.55 + Math.random() * 0.55,
        c: COLORS[Math.floor(Math.random() * COLORS.length)], t: 0
      });
    }
    kick();
  });
  hero.addEventListener("pointerleave", function () { px = py = -1; });
  hero.addEventListener("pointerdown", function (e) {
    if (!toggle.checked || e.pointerType !== "mouse") return;
    var r = hero.getBoundingClientRect();
    rings.push({ x: e.clientX - r.left + 4, y: e.clientY - r.top + 4, t: 0, i: rings.length });
    kick();
  });

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (en) { visible = en[0].isIntersecting; if (visible) kick(); }).observe(hero);
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) kick(); });
  window.addEventListener("resize", function () { clearTimeout(resize._t); resize._t = setTimeout(resize, 120); });

  // ------------------------------------------------------------------ Khởi động
  var saved = store("ez-lang");
  var start = saved || ((navigator.language || "").toLowerCase().indexOf("vi") === 0 ? "vi" : "en");
  applyToggle();
  resize();
  setLang(start);
  kick();
})();

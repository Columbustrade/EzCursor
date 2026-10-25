/*
 * Thông tin bạn tự điền cho trang web EzCursor.
 * Ô nào để trống ("") thì trang sẽ tự ẩn phần đó.
 * Ảnh (QR, ảnh trong game) đặt trong thư mục docs/images/.
 */
window.EZ_CONFIG = {
  // ---- Ủng hộ ----
  momo: {
    phone: "",            // vd: "0901234567"
    name: "",             // tên chủ ví, vd: "NGUYEN VAN A"
    qr: ""                // vd: "images/momo-qr.png"
  },
  bank: {
    bank: "",             // vd: "Vietcombank"
    account: "",          // số tài khoản
    name: "",             // tên chủ tài khoản
    qr: ""                // vd: "images/bank-qr.png"
  },
  paypal: {
    url: ""               // vd: "https://paypal.me/tencuaban"
  },

  // ---- Ảnh trong game ----
  // Thêm ảnh vào docs/images/ rồi khai báo ở đây. Chú thích có thể viết 2 thứ tiếng.
  gameShots: [
    { src: "images/game-1.jpg", vi: "Liquid Drop với vệt lấp lánh trong Last Epoch", en: "Liquid Drop with a sparkle trail in Last Epoch" },
    { src: "images/game-2.jpg", vi: "Con trỏ Bibata Amber giữa trận đánh", en: "Bibata Amber cursor mid-fight" },
    { src: "images/game-3.jpg", vi: "Hiệu ứng pháo hoa khi click", en: "Fireworks effect on click" }
  ]
};

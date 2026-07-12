/* ╔═══════════════════════════════════════════════════════════════╗
   ║  三國志11 武將選秀 — 連線設定                                  ║
   ║                                                               ║
   ║  這個檔案只需要填一次。日後更新 index.html 時不要動這個檔，     ║
   ║  你的設定就不會遺失。                                          ║
   ║                                                               ║
   ║  兩個值從哪裡來（詳見 連線版設定指南.md）：                     ║
   ║   apiKey       Firebase 主控台 → 專案設定 → 你的應用程式        ║
   ║   databaseURL  Realtime Database 頁面上方那串網址              ║
   ║                                                               ║
   ║  留空 = 單機模式（功能完全正常，只是無法多人連線）              ║
   ╚═══════════════════════════════════════════════════════════════╝ */

const SAN11_CONFIG = {
  apiKey: "AIzaSyCrKiXHlUcQZS9M4Ng2fk_H7L-3XFRhn3Y",
  databaseURL: "https://pvp-draft-default-rtdb.asia-southeast1.firebasedatabase.app",
};

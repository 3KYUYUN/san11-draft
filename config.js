/* ╔═══════════════════════════════════════════════════════════════╗
   ║  三國志11 武將選秀 — 連線設定（更新網頁時不要動這個檔）          ║
   ╚═══════════════════════════════════════════════════════════════╝ */

const SAN11_CONFIG = {
  /* ── Firebase（多人連線；留空 = 單機模式）──
     說明：apiKey 與 databaseURL 是 Firebase 網頁應用的「公開識別碼」，
     設計上就是放在前端的，本身不是密鑰；真正的安全由資料庫規則把關。
     建議搭配「連線版設定指南」第八節：啟用匿名驗證＋鎖緊規則。 */
  apiKey: "",
  databaseURL: "",

  /* ── Telegram 輪次通知 ──
     方式A（建議）：tgProxy 填 Cloudflare Worker 網址，token 藏在
       伺服器端（部署方法見 tg_worker.js 檔頭），tgToken 留空。
     方式B（簡易）：tgToken + tgChat 直連。token 會隨網頁公開，
       任何拿到網頁的人都能用這支 bot 發訊息，僅限私人社群。 */
  tgProxy: "https://tight-poetry-8100.3kyuyun.workers.dev/",
  tgToken: "",
  tgChat: "@ThreeKingdomsYuYun",
};

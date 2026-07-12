/* ╔═══════════════════════════════════════════════════════════════╗
   ║  三國志11 武將選秀 — 連線設定（更新網頁時不要動這個檔）          ║
   ╚═══════════════════════════════════════════════════════════════╝ */

const SAN11_CONFIG = {
  /* Firebase（多人連線；留空 = 單機模式）*/
  apiKey: "",
  databaseURL: "",

  /* Telegram 輪次通知（留空 = 不通知）
     ⚠ 注意：token 放在網頁端等於公開，任何拿到網頁的人都能用這支 bot
       發訊息。僅限自己社群使用；若外流，到 @BotFather 用 /revoke 換新。
     bot 必須先被加入目標群組才能發言。 */
  tgToken: "8661160761:AAEqyNibUaLZaiZNJcFj3pN-UAlbb_uZfYc",
  tgChat: "@ThreeKingdomsYuYun",
};

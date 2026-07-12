/* ╔═══════════════════════════════════════════════════════════════╗
   ║  Telegram 通知代理 — Cloudflare Worker（免費）                  ║
   ║                                                               ║
   ║  用途：把 bot token 藏在伺服器端，網頁端只呼叫這個代理，        ║
   ║  看網頁原始碼的人拿不到 token。                                ║
   ║                                                               ║
   ║  部署步驟（5 分鐘）：                                          ║
   ║  1. https://dash.cloudflare.com → Workers & Pages →            ║
   ║     Create Worker → 貼上本檔全部內容 → Deploy                  ║
   ║  2. Worker 的 Settings → Variables and Secrets → 新增兩個：    ║
   ║     TG_TOKEN = 你的 bot token（型別選 Secret）                  ║
   ║     TG_CHAT  = @ThreeKingdomsYuYun                             ║
   ║     （選填）ALLOW_ORIGIN = https://你的帳號.github.io           ║
   ║  3. 複製 Worker 網址（https://xxx.你的帳號.workers.dev），      ║
   ║     填到 config.js 的 tgProxy，並把 tgToken 清空               ║
   ║  4. 到 @BotFather 用 /revoke 換一組新 token（舊的已在網頁       ║
   ║     公開過），把新 token 填進 Worker 的 TG_TOKEN                ║
   ╚═══════════════════════════════════════════════════════════════╝ */

const RATE = new Map();   // 簡易速率限制：每 IP 每分鐘 10 則

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOW_ORIGIN || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "POST") return new Response("Method not allowed", { status: 405, headers: cors });

    // 來源檢查（瀏覽器內可靠；擋掉最常見的濫用）
    if (env.ALLOW_ORIGIN) {
      const origin = request.headers.get("Origin") || "";
      if (!origin.startsWith(env.ALLOW_ORIGIN)) {
        return new Response("Forbidden", { status: 403, headers: cors });
      }
    }

    // 速率限制
    const ip = request.headers.get("CF-Connecting-IP") || "?";
    const now = Date.now();
    const rec = RATE.get(ip) || { n: 0, t: now };
    if (now - rec.t > 60000) { rec.n = 0; rec.t = now; }
    if (++rec.n > 10) return new Response("Too many requests", { status: 429, headers: cors });
    RATE.set(ip, rec);

    // 轉發到 Telegram
    let body;
    try { body = await request.json(); } catch { return new Response("Bad request", { status: 400, headers: cors }); }
    const text = String(body.text || "").slice(0, 500);
    if (!text) return new Response("Empty", { status: 400, headers: cors });

    const resp = await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: env.TG_CHAT, text }),
    });
    return new Response(resp.ok ? "ok" : "tg error", { status: resp.ok ? 200 : 502, headers: cors });
  },
};

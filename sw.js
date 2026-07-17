/* 三國志11 武將選秀 — Service Worker
   策略：
   - App 殼層（HTML/圖示/manifest）：先網路後快取（network-first），
     確保你更新網頁後玩家立刻拿到新版；離線時回退到快取。
   - Firebase / Google 字型：不攔截，交給瀏覽器與 Firebase SDK 自行處理。
   改版時把 CACHE 的版本號 +1，舊快取會自動清掉。 */

const CACHE = "san11-draft-v38";
const SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./config.js",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-maskable-512.png",
  "./apple-touch-icon.png",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL).catch(() => {}))   // 個別檔案缺失不阻擋安裝
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // 只處理同源請求；Firebase、Google 字型等外部資源直接放行
  if (url.origin !== self.location.origin) return;

  e.respondWith(
    fetch(req)
      .then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req).then(hit => hit || caches.match("./index.html")))
  );
});

// 由頁面觸發立即更新
self.addEventListener("message", e => {
  if (e.data === "skipWaiting") self.skipWaiting();
});

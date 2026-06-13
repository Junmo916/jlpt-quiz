/* 日文背词 — Service Worker */

const CACHE_NAME = 'jlpt-quiz-v1';
const ASSETS = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './manifest.json',
];

// ── 安装时缓存核心资源 ──
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// ── 激活时清除旧缓存 ──
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── 拦截请求：缓存优先，网络回退 ──
self.addEventListener('fetch', event => {
  // 只缓存同源 GET 请求
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // 跳过 localStorage-like API
  if (url.pathname.includes('/_')) return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        // 只缓存 JSON 和核心资源
        if (response.ok && (
          event.request.url.endsWith('.json') ||
          event.request.url.endsWith('.html') ||
          event.request.url.endsWith('.css') ||
          event.request.url.endsWith('.js')
        )) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    })
  );
});

// Dashboard Service Worker (safe caching policy)
// - Never cache API responses (prevents stale auth/data)
// - Network-first for HTML/JS/CSS
// - Cache-first only for immutable assets/images
const CACHE_NAME = 'dashboard-cache-v2';
const CORE_ASSETS = [
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== 'GET') {
    return;
  }

  // Never cache API endpoints
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(req));
    return;
  }

  const isDocument = req.mode === 'navigate' || req.destination === 'document';
  const isCriticalStatic = url.pathname.startsWith('/static/') && /\.(js|css|html)$/i.test(url.pathname);

  // Network-first for pages and critical static files to avoid stale dashboard code
  if (isDocument || isCriticalStatic) {
    event.respondWith(
      fetch(req)
        .then(response => {
          if (response && response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(req, clone));
          }
          return response;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first for other static assets
  event.respondWith(
    caches.match(req).then(cached => {
      if (cached) return cached;
      return fetch(req).then(response => {
        if (response && response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, clone));
        }
        return response;
      });
    })
  );
});

// Push notifications
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Dashboard Notification';
  const options = {
    body: data.body || '',
    icon: '/assets/images/icon-192.png',
    badge: '/assets/images/icon-192.png',
    data: data.url || '/'
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data)
  );
});

// Background sync (stub)
self.addEventListener('sync', event => {
  if (event.tag === 'dashboard-sync') {
    // Implement background sync logic here
  }
});

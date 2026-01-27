// Simple service worker for PWA support
self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', event => {
  // Optionally add caching logic here
});

// Additional existing code can be removed or commented out as needed
// const CACHE_NAME = 'dashboard-cache-v1';
// const urlsToCache = [
//   '/',
//   '/static/manifest.json',
//   '/static/styles.css',
//   '/static/app.js',
//   // Add more assets as needed
// ];
const CACHE_NAME = 'dashboard-cache-v1';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/static/styles.css',
  '/static/app.js',
  // Add more assets as needed
];


self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request).then(networkResponse => {
          // Dynamic caching for GET requests
          if (event.request.method === 'GET') {
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, networkResponse.clone());
            });
          }
          return networkResponse;
        });
      })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
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

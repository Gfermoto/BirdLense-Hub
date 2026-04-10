import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching';
import { clientsClaim } from 'workbox-core';

// skipWaiting по сообщению от клиента (когда пользователь нажмёт «Обновить»)
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});
clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = {
      title: 'BirdLense',
      body: event.data.text() || 'New detection',
    };
  }
  const title = payload.title || 'BirdLense';
  const body = payload.body || '';
  const tag = payload.tag || 'detection';
  const url = payload.url || '/';
  const options = {
    body,
    tag,
    icon: '/web-app-manifest-192x192.png',
    badge: '/favicon.svg',
    data: { url },
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification?.data?.url || '/';
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.navigate(url);
            return client.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(
            url.startsWith('/') ? self.location.origin + url : url,
          );
        }
      }),
  );
});

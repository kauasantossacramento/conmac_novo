// Instalação: cache inicial
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('v1').then(cache => {
      return cache.addAll([
        '/',
        '/static/css/style.css',
        '/static/js/app.js'
      ]);
    })
  );
});

// Intercepta requisições e responde com cache ou rede
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

// Recebe notificações push
self.addEventListener('push', event => {
  const data = event.data.json();

  const title = data.head || 'Nova notificação';
  const options = {
    body: data.body || '',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-192x192.png'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});
self.addEventListener("install", event => {
  console.log("Service Worker instalado");
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  console.log("Service Worker ativado");
});

self.addEventListener("push", event => {
  const data = event.data.json();
  self.registration.showNotification(data.head, {
    body: data.body,
    icon: "/static/icons/icon-192x192.png",
  });
});
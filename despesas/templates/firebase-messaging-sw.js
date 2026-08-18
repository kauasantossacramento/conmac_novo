importScripts('https://www.gstatic.com/firebasejs/10.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.0.0/firebase-messaging-compat.js');

const firebaseConfig = {
    apiKey: "AIzaSyDIJm4fS7o1m7VgvfFU-9WpIi0i-uKUyug",
    authDomain: "conmac-app.firebaseapp.com",
    projectId: "conmac-app",
    storageBucket: "conmac-app.firebasestorage.app",
    messagingSenderId: "199472856868",
    appId: "1:199472856868:web:7bd0fb536fbe63d9007db1",
    measurementId: "G-F4FH3KGGFS"
};

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// 1. Recebimento em Background
messaging.onBackgroundMessage(function(payload) {
  console.log('Notificação Background:', payload);

  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/static/img/logo_conmac.png',
    // Passamos o link dentro do objeto data
    data: payload.data 
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

// 2. Evento de CLIQUE na notificação
self.addEventListener('notificationclick', function(event) {
  console.log('Notificação clicada!');
  
  event.notification.close(); // Fecha a notificação

  // Recupera o link que enviamos no admin (ou vai para a home)
  const linkParaAbrir = event.notification.data.link || '/';

  event.waitUntil(
    clients.matchAll({type: 'window'}).then(windowClients => {
      // Tenta focar numa aba já aberta
      for (var i = 0; i < windowClients.length; i++) {
        var client = windowClients[i];
        if (client.url === linkParaAbrir && 'focus' in client) {
          return client.focus();
        }
      }
      // Se não tiver aba aberta, abre uma nova
      if (clients.openWindow) {
        return clients.openWindow(linkParaAbrir);
      }
    })
  );
});
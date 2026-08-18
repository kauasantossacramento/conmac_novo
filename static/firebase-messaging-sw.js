// static/firebase-messaging-sw.js
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

// Opcional: Manipular notificação em background
messaging.onBackgroundMessage(function(payload) {
  console.log('Notificação recebida em background: ', payload);
  
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/static/images/logo.png' // Coloque o caminho do seu logo aqui
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});
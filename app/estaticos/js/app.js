// Práctica 13: registra el service worker (instalar la app y ver algo útil sin red).
if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
}

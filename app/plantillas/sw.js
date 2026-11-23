/* Titicaca Vivo · service worker (Práctica 13). Lo sirve /sw.js con alcance en todo el sitio.

   La regla que no se negocia: lo de una persona (su reserva, su sesión, el panel del personal)
   va SOLO por la red y nunca entra a la caché del celular: el celular se presta, se pierde, se
   comparte. Sin red, esas páginas muestran «Sin conexión», no una copia vieja. */

const CACHE = "titicaca-vivo-{{ config.VERSION }}";
const SIN_CONEXION = "/sin-conexion";

// Lo que se guarda al instalar: la pantalla «Sin conexión» y lo que necesita para verse.
const AL_INSTALAR = [
  "/sin-conexion",
  "{{ estatico('css/estilos.css') }}",
  "{{ estatico('js/app.js') }}",
  "{{ estatico('img/logo-isotipo.svg') }}",
  "{{ estatico('img/favicon.svg') }}",
  "/estaticos/img/fondo-tejido.svg",
  "/estaticos/img/fondo-lago.svg",
  "/estaticos/img/olas.svg",
];

// De una persona: SOLO por la red. Sin red, «Sin conexión». Nunca se guardan.
const SOLO_RED = ["/panel", "/mi-reserva", "/reservas/", "/entrar", "/salir", "/recuperar", "/api/",
                  "/catalogos", "/idioma/", "/contacto", "/libro-de-reclamaciones", "/grupos"];

// Páginas públicas: primero la red; sin red, la última copia que se vio (si no es de una persona).
const PUBLICAS = ["/salidas", "/comunidades", "/alertas", "/experiencias", "/productos", "/galeria",
                  "/privacidad", "/condiciones"];

function esDeUnaPersona(ruta) {
  return SOLO_RED.some((p) => ruta.startsWith(p)) || ruta.endsWith("/reservar");
}

function esPublica(ruta) {
  return ruta === "/" || PUBLICAS.some((p) => ruta === p || ruta.startsWith(p + "/"));
}

// Guarda una copia solo si el servidor lo permite: con la sesión abierta todo viene «no-store».
function guardar(pedido, respuesta) {
  const control = respuesta.headers.get("Cache-Control") || "";
  if (respuesta.ok && respuesta.type === "basic" && !/no-store|private/.test(control)) {
    const copia = respuesta.clone();
    caches.open(CACHE).then((cache) => cache.put(pedido, copia));
  }
  return respuesta;
}

self.addEventListener("install", (evento) => {
  // credentials: "omit": lo que se guarda al instalar se pide sin la sesión, así no lleva nombres.
  const pedidos = AL_INSTALAR.map((url) => new Request(url, { credentials: "omit" }));
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(pedidos)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(caches.keys()
    .then((nombres) => Promise.all(nombres.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  const url = new URL(pedido.url);
  if (pedido.method !== "GET" || url.origin !== self.location.origin) {
    return;                                         // POST y lo de otros sitios: como siempre
  }
  const ruta = url.pathname;
  if (esDeUnaPersona(ruta)) {
    if (pedido.mode === "navigate") {
      evento.respondWith(fetch(pedido).catch(() => caches.match(SIN_CONEXION)));
    }
    return;                                         // solo red: nada de esto se guarda
  }
  if (ruta.startsWith("/estaticos/")) {             // estilos, scripts e imágenes: caché primero
    evento.respondWith(caches.match(pedido).then((guardado) =>
      guardado || fetch(pedido).then((respuesta) => guardar(pedido, respuesta))));
    return;
  }
  if (pedido.mode === "navigate") {
    if (esPublica(ruta)) {                          // red primero; sin red, la copia o «Sin conexión»
      evento.respondWith(fetch(pedido).then((respuesta) => guardar(pedido, respuesta))
        .catch(() => caches.match(pedido).then((guardado) => guardado || caches.match(SIN_CONEXION))));
    } else {
      evento.respondWith(fetch(pedido).catch(() => caches.match(SIN_CONEXION)));
    }
  }
});

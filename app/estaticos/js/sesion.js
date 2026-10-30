// Cierre de la sesión por inactividad (D-110). El que cierra la sesión es el servidor; esto solo:
//  - le avisa que la persona sigue trabajando (escribe, hace clic, se mueve en la página),
//    como mucho una vez por minuto, aunque no cambie de página;
//  - muestra un aviso 2 minutos antes del cierre, con un botón para seguir;
//  - al llegar la hora, recarga la página: el servidor cierra la sesión y lleva a /entrar.
// Sin JavaScript la sesión se cierra igual (lo revisa el servidor en cada clic).
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || !window.fetch) { return; }
  var minutos = parseInt(script.getAttribute("data-minutos"), 10);
  var url = script.getAttribute("data-url");
  if (!minutos || !url) { return; }

  var limite = minutos * 60000;
  var ultimaActividad = Date.now();
  var ultimoAvisoAlServidor = Date.now();
  var aviso = null;

  function recargar() { window.location.reload(); }

  function avisarAlServidor() {
    ultimoAvisoAlServidor = Date.now();
    fetch(url, { credentials: "same-origin", cache: "no-store" }).then(function (respuesta) {
      // 401: la sesión ya se cerró; redirigida: el servidor la mandó a /entrar
      if (respuesta.status === 401 || respuesta.redirected) { recargar(); }
    }).catch(function () { /* sin señal: se vuelve a intentar con el siguiente clic */ });
  }

  function quitarAviso() {
    if (aviso) { aviso.remove(); aviso = null; }
  }

  function actividad() {
    ultimaActividad = Date.now();
    quitarAviso();
    if (Date.now() - ultimoAvisoAlServidor > 60000) { avisarAlServidor(); }
  }

  function mostrarAviso(restanMinutos) {
    if (aviso) { return; }
    aviso = document.createElement("div");
    aviso.className = "aviso aviso--info aviso-sesion";
    aviso.setAttribute("role", "alert");
    var texto = document.createElement("p");
    texto.textContent = "Tu sesión se cerrará en " + restanMinutos + " minuto" +
      (restanMinutos > 1 ? "s" : "") + " por inactividad.";
    var boton = document.createElement("button");
    boton.type = "button";
    boton.className = "boton boton--chico";
    boton.textContent = "Seguir trabajando";
    boton.addEventListener("click", function () { actividad(); avisarAlServidor(); });
    aviso.appendChild(texto);
    aviso.appendChild(boton);
    document.body.appendChild(aviso);
    boton.focus();
  }

  ["pointerdown", "keydown", "input", "scroll", "touchstart"].forEach(function (evento) {
    document.addEventListener(evento, actividad, { passive: true, capture: true });
  });

  window.setInterval(function () {
    var resta = limite - (Date.now() - ultimaActividad);
    if (resta <= 0) { recargar(); return; }
    if (resta <= 120000) { mostrarAviso(Math.max(1, Math.ceil(resta / 60000))); }
  }, 10000);
})();

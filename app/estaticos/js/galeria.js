// Galería (v2.5): al tocar una foto se abre en grande en un <dialog>, con su nombre, su texto y
// su crédito. Anterior y siguiente con los botones o con las flechas del teclado; Esc o
// «Cerrar» lo cierran y el foco vuelve a la foto. Sin JavaScript (o con Ctrl+clic), cada foto
// lleva a la página de su comunidad.
(function () {
  "use strict";
  var visor = document.getElementById("visor");
  var fotos = Array.prototype.slice.call(document.querySelectorAll(".galeria__enlace"));
  if (!visor || typeof visor.showModal !== "function" || !fotos.length) { return; }
  var imagen = visor.querySelector(".visor__imagen");
  var titulo = visor.querySelector(".visor__titulo");
  var texto = visor.querySelector(".visor__texto");
  var credito = visor.querySelector(".visor__credito");
  var ir = visor.querySelector(".visor__ir");
  var actual = 0;

  function mostrar(indice) {
    actual = (indice + fotos.length) % fotos.length;       // de la última vuelve a la primera
    var foto = fotos[actual];
    imagen.src = foto.getAttribute("data-foto");
    imagen.alt = foto.getAttribute("data-alt");
    titulo.textContent = foto.getAttribute("data-nombre");
    texto.textContent = foto.getAttribute("data-texto");
    credito.textContent = foto.getAttribute("data-credito");
    ir.href = foto.getAttribute("href");
  }

  fotos.forEach(function (foto, indice) {
    foto.addEventListener("click", function (evento) {
      if (evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0) { return; }
      evento.preventDefault();
      mostrar(indice);
      visor.showModal();
    });
  });
  visor.querySelector(".visor__anterior").addEventListener("click", function () { mostrar(actual - 1); });
  visor.querySelector(".visor__siguiente").addEventListener("click", function () { mostrar(actual + 1); });
  visor.querySelector(".visor__cerrar").addEventListener("click", function () { visor.close(); });
  visor.addEventListener("keydown", function (evento) {
    if (evento.key === "ArrowLeft") { mostrar(actual - 1); }
    if (evento.key === "ArrowRight") { mostrar(actual + 1); }
  });
  // Un clic en el fondo oscuro (fuera de la foto) también cierra
  visor.addEventListener("click", function (evento) { if (evento.target === visor) { visor.close(); } });
  visor.addEventListener("close", function () { fotos[actual].focus(); });
})();

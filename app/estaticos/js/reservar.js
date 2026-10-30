// Formulario de reserva: agregar y quitar acompañantes sin recargar la página.
// Sin JavaScript también funciona: se elige la cantidad y la página se recarga (selector-cantidad).
(function () {
  "use strict";
  var lista = document.getElementById("acompanantes");
  var plantilla = document.getElementById("plantilla-acompanante");
  var agregar = document.getElementById("agregar-acompanante");
  var selector = document.getElementById("selector-cantidad");
  if (!lista || !plantilla || !agregar) { return; }

  var maximo = parseInt(lista.getAttribute("data-maximo"), 10) || 9;
  if (selector) { selector.hidden = true; }      // con JS no hace falta recargar
  agregar.hidden = false;

  function filas() { return lista.querySelectorAll(".pasajero"); }

  // Vuelve a numerar name, id, for y aria-describedby (acompanantes-0-, -1-, ...)
  function renumerar() {
    Array.prototype.forEach.call(filas(), function (fila, i) {
      fila.querySelectorAll("[name], [id], [for], [aria-describedby]").forEach(function (el) {
        ["name", "id", "for", "aria-describedby"].forEach(function (atributo) {
          var valor = el.getAttribute(atributo);
          if (valor) { el.setAttribute(atributo, valor.replace(/acompanantes-\d+-/g, "acompanantes-" + i + "-")); }
        });
      });
      var numero = fila.querySelector(".pasajero__numero");
      if (numero) { numero.textContent = i + 1; }
      var quitar = fila.querySelector(".quitar-acompanante");
      if (quitar) { quitar.hidden = false; }
    });
    agregar.disabled = filas().length >= maximo;
  }

  agregar.addEventListener("click", function () {
    var indice = filas().length;
    if (indice >= maximo) { return; }
    var html = plantilla.innerHTML.replace(/__I__/g, String(indice)).replace(/__N__/g, String(indice + 1));
    lista.insertAdjacentHTML("beforeend", html);
    renumerar();
    var nueva = filas()[indice];
    nueva.querySelector("input").focus();
  });

  lista.addEventListener("click", function (evento) {
    var boton = evento.target.closest(".quitar-acompanante");
    if (!boton) { return; }
    boton.closest(".pasajero").remove();
    renumerar();
    agregar.focus();
  });

  renumerar();
})();

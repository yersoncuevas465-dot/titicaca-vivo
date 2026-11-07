// DNI → nombres y apellidos (RENIEC) en el formulario de reserva (v2.2).
// Al completar los 8 dígitos de un DNI se piden los nombres a /api/dni (con el token CSRF del
// formulario); el servidor consulta RENIEC. Solo se escribe en campos vacíos o que ya llenó
// RENIEC: lo que escribió la persona se respeta. Si RENIEC no responde, se escribe a mano y
// el formulario sigue igual. Sin JavaScript, el formulario funciona como siempre.
(function () {
  "use strict";
  var formulario = document.querySelector("form[data-dni-url]");
  if (!formulario || !window.fetch || !window.URLSearchParams) { return; }
  var url = formulario.getAttribute("data-dni-url");
  var token = formulario.querySelector("input[name='csrf_token']");
  var consultado = {};                 // por campo: el último DNI consultado (no se repite)
  var esperas = {};

  // "titular_numero_documento" → "titular_"; "acompanantes-2-tipo_documento" → "acompanantes-2-"
  function prefijo(campo) { return campo.name.replace(/(numero|tipo)_documento$/, ""); }
  function hermano(campo, nombre) {
    return formulario.querySelector("[name='" + prefijo(campo) + nombre + "']");
  }

  // Línea de estado debajo del número (role=status: el lector de pantalla la anuncia)
  function estado(campo, texto) {
    var p = campo.parentNode.querySelector(".campo__reniec");
    if (!p) {
      p = document.createElement("p");
      p.className = "campo__ayuda campo__reniec";
      p.setAttribute("role", "status");
      campo.insertAdjacentElement("afterend", p);
    }
    p.textContent = texto;
  }

  function borrarEstado(campo) {
    var p = campo.parentNode.querySelector(".campo__reniec");
    if (p) { p.remove(); }
  }

  function completar(campo, nombre, valor) {
    var destino = hermano(campo, nombre);
    if (destino && (!destino.value.trim() || destino.getAttribute("data-reniec") === "1")) {
      destino.value = valor;
      destino.setAttribute("data-reniec", "1");
    }
  }

  function consultar(numero) {
    var tipo = hermano(numero, "tipo_documento");
    var dni = numero.value.replace(/[\s.\-]/g, "");
    if (!tipo || tipo.value !== "DNI" || !/^\d{8}$/.test(dni)) {     // ya no es un DNI completo
      borrarEstado(numero);
      consultado[numero.name] = null;
      return;
    }
    if (consultado[numero.name] === dni) { return; }
    consultado[numero.name] = dni;
    estado(numero, formulario.getAttribute("data-dni-buscando"));
    fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: {"X-CSRFToken": token ? token.value : ""},
      body: new URLSearchParams({dni: dni, csrf_token: token ? token.value : ""})
    })
      .then(function (r) { return r.json().catch(function () { return {ok: false}; }); })
      .then(function (r) {
        if (numero.value.replace(/[\s.\-]/g, "") !== dni) { return; }     // ya cambió el número
        if (r.ok) {
          completar(numero, "nombres", r.nombres);
          completar(numero, "apellidos", r.apellidos);
          var pais = hermano(numero, "nacionalidad");
          if (pais && !pais.value.trim()) { pais.value = "Perú"; }          // DNI = peruano
          estado(numero, formulario.getAttribute("data-dni-listo")
            .replace("{nombre}", r.nombres + " " + r.apellidos));
        } else {
          estado(numero, r.error || formulario.getAttribute("data-dni-error"));
          if (!r.error) { consultado[numero.name] = null; }              // se puede reintentar
        }
      })
      .catch(function () {
        consultado[numero.name] = null;
        estado(numero, formulario.getAttribute("data-dni-error"));
      });
  }

  // Al escribir (con una pausa corta) y al cambiar el tipo de documento a DNI
  formulario.addEventListener("input", function (evento) {
    var campo = evento.target;
    // Si la persona corrige un nombre que llenó RENIEC, ese campo pasa a ser suyo
    if (campo.hasAttribute("data-reniec")) { campo.removeAttribute("data-reniec"); }
    if (!campo.name || !/numero_documento$/.test(campo.name)) { return; }
    clearTimeout(esperas[campo.name]);
    esperas[campo.name] = setTimeout(function () { consultar(campo); }, 350);
  });
  formulario.addEventListener("change", function (evento) {
    var campo = evento.target;
    if (campo.name && /tipo_documento$/.test(campo.name)) {
      var numero = hermano(campo, "numero_documento");
      if (numero) { consultar(numero); }
    }
  });
})();

// Práctica 13: en el celular, cada fila de una tabla del panel se ve como una tarjeta y cada dato
// lleva su título (sale del encabezado de su columna). Así «Verificar» o «Suspender» quedan a la
// vista sin correr la tabla de costado. Sin JavaScript, la tabla se sigue pudiendo desplazar.
document.querySelectorAll(".tabla-desplazable .tabla").forEach((tabla) => {
  const titulos = [...tabla.querySelectorAll("thead th")].map((th) => th.textContent.trim());
  if (!titulos.length) return;
  tabla.querySelectorAll("tbody tr").forEach((fila) => {
    [...fila.children].forEach((celda, i) => {
      if (titulos[i] && !celda.dataset.titulo) celda.dataset.titulo = titulos[i];
    });
  });
  tabla.classList.add("tabla--tarjetas");
});

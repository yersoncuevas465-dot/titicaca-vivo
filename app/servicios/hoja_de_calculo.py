"""Archivos CSV para Excel (la bitácora y el reporte general de los respaldos).

- Llevan \ufeff al inicio: así Excel abre las tildes y la ñ bien (UTF-8).
- Una celda que empieza con = + - @ Excel la tomaría como fórmula: se le antepone un apóstrofo
  (un motivo o un nombre escrito por alguien no puede ejecutar nada al abrir el archivo).
"""

import csv
import io
import zipfile


def celda(valor):
    """Un valor listo para el CSV."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def csv_para_excel(encabezados, filas):
    """El texto del CSV (con la marca UTF-8 al inicio)."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(encabezados)
    for fila in filas:
        escritor.writerow([celda(valor) for valor in fila])
    return "\ufeff" + salida.getvalue()


def zip_de_csv(hojas, leeme):
    """Un ZIP con un CSV por hoja ({nombre: (encabezados, filas)}) y un LEEME.txt."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", compression=zipfile.ZIP_DEFLATED) as zip_:
        for nombre, (encabezados, filas) in hojas.items():
            zip_.writestr(f"{nombre}.csv", csv_para_excel(encabezados, filas))
        zip_.writestr("LEEME.txt", leeme.replace("\n", "\r\n"))
    return memoria.getvalue()

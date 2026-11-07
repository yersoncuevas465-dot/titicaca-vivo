# Acta de aceptación · Titicaca Vivo

| Dato | Valor |
|---|---|
| Curso | EST323 · Ingeniería de Software II · FINESI · UNA Puno · 2026-II |
| Versión probada | 2.9.1 |
| Fecha | ___/11/2026 |
| Equipo que entrega | Yerson Cuevas · Zulema Luque · Shanell Ilaquita|
| Mesa que ejecuta | ___________________________ |

**Cómo se prueba:** con la app abierta (`INICIAR.bat`) y los usuarios de `USUARIOS_DEMO.txt`.
En cada caso la mesa marca **Pasó** o **No pasó**; si no pasó, anota qué vio.

| N.º | Dado | Cuando | Entonces | Resultado | Observación |
|---|---|---|---|---|---|
| 1 | una salida a los Uros con lugares libres | el turista reserva para 2 personas con sus datos | recibe un código TV-XXXX y la reserva queda «pendiente de pago» | | |
| 2 | una salida con 2 lugares libres | el turista intenta reservar para 3 personas | el sistema no lo deja y le dice «Solo quedan 2 lugares en esta salida» | | |
| 3 | una reserva pendiente de pago | el turista reporta su Yape con el número de operación y el operador lo verifica en «Pagos» | la reserva pasa a «pagada» y en «Mi reserva» aparece el boleto con QR | | |
| 4 | la reserva TV-33VR del titular con DNI 40998812 | el turista entra a «Mi reserva» con ese código y ese DNI | ve su reserva pagada y su boleto con QR para el embarque | | |
| 5 | salidas programadas que pasan por Amantaní | el operador registra una alerta roja de oleaje en Amantaní y pulsa «Suspender las salidas en un solo paso» | esas salidas quedan suspendidas y el turista ve el motivo y la opción de reprogramar o pedir la devolución | | |
| 6 | la residente de Taquile con su cuenta (residente.juana) | publica un producto con su precio y su foto | el producto aparece en «Productos» de Taquile con su nombre y dónde encontrarlo | | |
| 7 | la residente de Taquile con su cuenta | intenta abrir «Salidas» del panel (/panel/salidas) | el sistema le dice que no tiene permiso: solo ve sus productos | | |
| 8 | un turista en la página «Libro de reclamaciones» | registra una hoja con sus datos y su reclamo | recibe el número correlativo de la hoja y la constancia con el plazo de 15 días hábiles | | |

**Resultado general:** ___ de 8 casos pasaron.

| Firma de la mesa que ejecuta | Firma del equipo |
|---|---|
| | |
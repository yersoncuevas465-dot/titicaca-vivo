"""Diccionario español → inglés de las páginas del turista (sección 8.9).

Clave: el texto tal como está en español en la plantilla o en el código. Las {marcas} se
mantienen iguales en las dos versiones. Una prueba (test_idioma.py) revisa que cada t('…')
de las plantillas del turista tenga su traducción aquí.
"""

import re

EN = {
    # --- Cabecera, menú y pie -----------------------------------------------------------------
    "Salidas en lancha y turismo vivencial en el lago Titicaca, Puno.":
        "Boat trips and community-based tourism on Lake Titicaca, Puno.",
    "Saltar al contenido": "Skip to content",
    "Foto de fondo: {credito}": "Background photo: {credito}",
    "Sale de Puno": "Leaves from Puno",
    "Vuelve a Puno": "Returns to Puno",
    "El recorrido": "The route",
    "Las paradas numeradas son el orden de visita. Las demás rutas se ven tenues.": "Numbered stops show the order of the visits. Other routes are faded.",
    "La comunidad está resaltada con un halo; las rutas que paran aquí, con línea continua.": "The community is highlighted with a halo; the routes that stop here, with a solid line.",
    "Dónde queda": "Where it is",
    "Salir": "Log out",
    "Entrar": "Staff login",
    "Principal": "Main",
    "Inicio": "Home",
    "Salidas": "Departures",
    "Comunidades": "Communities",
    "Alertas": "Alerts",
    "Mi reserva": "My booking",
    "Titicaca Vivo · Puno, Perú · Horarios en hora de Lima":
        "Titicaca Vivo · Puno, Peru · Times in Lima time (UTC−5)",

    # --- Portada --------------------------------------------------------------------------------
    "Salidas en lancha por el lago Titicaca": "Boat trips on Lake Titicaca",
    "Vive el lago con las comunidades que lo habitan": "Experience the lake with the communities who live on it",
    "Elige tu salida en lancha, reserva tu lugar y duerme en casa de una familia anfitriona.":
        "Choose your boat trip, book your seat and stay overnight with a host family.",
    "Ver todas las salidas": "See all departures",
    "Alertas en el lago": "Alerts on the lake",
    "Salidas de hoy": "Today's departures",
    "Hoy no hay salidas programadas.": "There are no departures scheduled today.",
    "Ver las salidas de mañana →": "See tomorrow's departures →",
    "El lago y sus rutas": "The lake and its routes",
    "incluye una noche con una familia": "includes a night with a family",
    "desde": "from",
    "Adulto desde": "Adults from",
    "{n} familias anfitrionas": "{n} host families",
    "1 familia anfitriona": "1 host family",
    "Cómo reservar": "How to book",
    "Elige tu salida": "Choose your trip",
    "Mira el día, la ruta, el precio y los lugares libres.":
        "Check the day, the route, the price and the seats left.",
    "Escribe los datos": "Enter the details",
    "Los de cada pasajero y cómo vas a pagar: Yape, Plin o en el muelle.":
        "For each passenger, and how you will pay: Yape, Plin or at the dock.",
    "Guarda tu código": "Keep your code",
    "Al terminar recibes tu código TV-XXXX y tu boleto con QR para subir a la lancha.":
        "When you finish you get your TV-XXXX code and a ticket with a QR code to board the boat.",
    "¿Ya reservaste? Mira tu reserva con tu código →": "Already booked? See your booking with your code →",
    "¿Todavía no tienes código? Lo recibes al terminar tu reserva y también está en tu boleto.":
        "No code yet? You get it when you finish booking, and it is also on your ticket.",
    "Elegir una salida": "Choose a trip",

    # --- Salidas y tarjetas ---------------------------------------------------------------------
    "Salidas del {fecha}": "Departures on {fecha}",
    "Revisa la búsqueda": "Check your search",
    "Fecha": "Date",
    "Ruta": "Route",
    "Todas las rutas": "All routes",
    "Buscar": "Search",
    "Próximos días": "Next days",
    "Hoy": "Today",
    "{n} salida": "{n} departure",
    "{n} salidas": "{n} departures",
    "No hay salidas para esta fecha y esta ruta. Prueba con otro día.":
        "There are no departures for this date and route. Try another day.",
    "No hay salidas para esta fecha. Prueba con otro día.":
        "There are no departures for this date. Try another day.",
    "Escribe la fecha como año-mes-día, por ejemplo 2026-10-21.":
        "Write the date as year-month-day, for example 2026-10-21.",
    "Elige una fecha dentro del próximo año.": "Choose a date within the next year.",
    "Esa ruta no existe. Elige una de la lista.": "That route does not exist. Choose one from the list.",
    "Vuelve {cuando}": "Back {cuando}",
    "con noche en casa de una familia": "with a night at a family's home",
    "Hay una alerta en el lago para este horario": "There is a lake alert for this time",
    "Fuente: {fuente}": "Source: {fuente}",
    "desde {fecha}": "from {fecha}",
    "hasta {fecha}": "until {fecha}",
    "Vista de {nombre}": "View of {nombre}",
    "{ocupados} de {cupo} lugares ocupados": "{ocupados} of {cupo} seats taken",
    "{libres} libres": "{libres} left",
    "{n} libres": "{n} seats left",
    "Revisa el formulario": "Please check the form",

    # --- Detalle de una salida ------------------------------------------------------------------
    "{fecha}, zarpa a las {hora} y vuelve el {vuelta}.": "{fecha}, departs at {hora} and returns {vuelta}.",
    "Salida suspendida:": "Departure suspended:",
    "Alertas que afectan esta salida": "Alerts affecting this departure",
    "Lugares": "Seats",
    "Lancha": "Boat",
    "Sale de": "Departs from",
    "Duración": "Duration",
    "Reservar": "Book",
    "La reserva en línea estará disponible muy pronto.": "Online booking will be available very soon.",
    "Recorrido": "Itinerary",
    "noche con una familia": "night with a family",
    "Precios por persona": "Prices per person",
    "Esta fecha cae en la temporada {temporada}: los precios incluyen un recargo de {recargo} %.":
        "This date falls in the {temporada} season: prices include a {recargo} % surcharge.",
    "Pasajero": "Passenger",
    "Edad": "Age",
    "Precio": "Price",
    "{min} a {max} años": "{min} to {max} years",
    "{min} años o más": "{min} years or older",
    "El tipo de pasajero se verifica con el documento en el muelle.":
        "The passenger type is checked against the ID document at the pier.",
    "Esta salida todavía no tiene precios publicados.": "This departure has no published prices yet.",
    "Opiniones de quienes hicieron esta ruta": "Reviews from travellers on this route",
    "{promedio} de 5 · {total} opiniones": "{promedio} out of 5 · {total} reviews",
    "{n} de 5 estrellas": "{n} out of 5 stars",
    "Turista de {pais} · {fecha}": "Traveller from {pais} · {fecha}",

    # --- Comunidades y mapa -----------------------------------------------------------------------
    "Comunidades del lago": "Lake communities",
    "Cada comunidad organiza su turismo. Al reservar una ruta con noche, la familia anfitriona se asigna por turnos, para que todas reciban visitantes.":
        "Each community organises its own tourism. When you book a route with an overnight stay, "
        "the host family is assigned in turns, so every family receives visitors.",
    "Sin familias anfitrionas registradas": "No host families registered",
    "en 1 ruta": "on 1 route",
    "en {n} rutas": "on {n} routes",
    "Distrito": "District",
    "Idioma originario": "Indigenous language",
    "Señal de celular": "Mobile signal",
    "Artesanía": "Crafts",
    "1 familia ofrece taller textil": "1 family offers a weaving workshop",
    "{n} familias ofrecen taller textil": "{n} families offer a weaving workshop",
    "Pregunta en la visita": "Ask during your visit",
    "La señal es limitada: guarda tu boleto en el celular antes de salir de Puno.":
        "The signal is limited: save your ticket on your phone before leaving Puno.",
    "Próximas salidas que pasan por {nombre}": "Upcoming departures stopping at {nombre}",
    "con noche aquí": "overnight here",
    "Rutas que la visitan": "Routes that visit it",
    "parada {n}": "stop {n}",
    "se duerme aquí": "overnight stop",
    "Familias anfitrionas": "Host families",
    "Solo mostramos el nombre de la casa, cuántas personas recibe y qué ofrece. Los datos de contacto los tiene la agencia.":
        "We only show the name of the house, how many people it hosts and what it offers. "
        "The agency keeps the contact details.",
    "Hasta {n} personas": "Up to {n} people",
    "Esta comunidad todavía no tiene familias anfitrionas registradas.":
        "This community has no host families registered yet.",
    "Mapa esquemático de la bahía de Puno y sus comunidades": "Schematic map of Puno Bay and its communities",
    "Cada punto es una comunidad y lleva a su página. Las líneas son las rutas. Las mismas comunidades están en la lista de esta página.":
        "Each dot is a community and links to its page. The lines are the routes. "
        "The same communities are listed on this page.",
    "Comunidad quechua": "Quechua community",
    "Comunidad aimara": "Aymara community",
    "Mapa esquemático: las distancias son aproximadas.": "Schematic map: distances are approximate.",

    # --- Alertas ----------------------------------------------------------------------------------
    "Alertas del lago": "Lake alerts",
    "Avisos de SENAMHI, de la Capitanía de Puerto, de la agencia y de las comunidades. Con alerta naranja o roja, las salidas afectadas pueden suspenderse.":
        "Warnings from SENAMHI (the weather service), the Port Authority, the agency and the "
        "communities. With an orange or red alert, affected departures may be suspended.",
    "Vigentes ahora": "Active now",
    "No hay alertas vigentes. ¡Buen día para navegar!": "No active alerts. A good day to sail!",
    "Próximas": "Upcoming",
    "De los últimos 30 días": "From the last 30 days",

    # --- Etiquetas (servicios/formato.py) -------------------------------------------------------
    "Disponible": "Available",
    "Pocos cupos": "Few seats left",
    "Llena": "Full",
    "Suspendida": "Suspended",
    "Zarpó": "Departed",
    "Cancelada": "Cancelled",
    "Pendiente de pago": "Awaiting payment",
    "Confirmada (pagas en el muelle)": "Confirmed (pay at the pier)",
    "Pagada": "Paid",
    "Abordada": "Boarded",
    "Vencida (no se pagó a tiempo)": "Expired (not paid in time)",
    "No se presentó": "No-show",
    "Yape": "Yape",
    "Plin": "Plin",
    "En el muelle": "At the pier",
    "Efectivo en el muelle": "Cash at the pier",
    "Transferencia": "Bank transfer",
    "Tarjeta (POS)": "Card (POS)",
    "Por verificar": "Being checked",
    "Verificado": "Verified",
    "Rechazado": "Rejected",
    "Verde": "Green",
    "Amarilla": "Yellow",
    "Naranja": "Orange",
    "Roja": "Red",
    "Oleaje": "High waves",
    "Tormenta": "Storm",
    "Helada": "Frost",
    "Neblina": "Fog",
    "Granizo": "Hail",
    "Aviso": "Notice",
    "Quechua": "Quechua",
    "Aimara": "Aymara",
    "Buena señal": "Good signal",
    "Señal débil": "Weak signal",
    "Sin señal": "No signal",
    "Desayuno": "Breakfast",
    "Almuerzo": "Lunch",
    "Cena": "Dinner",
    "Vestimenta típica": "Traditional clothing",
    "Taller textil": "Weaving workshop",

    # --- Reservar ---------------------------------------------------------------------------------
    "Volver a la salida": "Back to the departure",
    "zarpa a las {hora}": "departs at {hora}",
    "Incluye una noche en casa de una familia anfitriona. La familia se asigna por turnos, para que todas reciban visitantes.":
        "Includes a night at a host family's home. Families are assigned in turns, so every "
        "family receives visitors.",
    "Esta salida ya no recibe reservas.": "This departure is no longer taking bookings.",
    "Busca otra salida": "Find another departure",
    "Revisa la reserva": "Please check your booking",
    "¿Cuántos acompañantes viajan contigo?": "How many people are travelling with you?",
    "Al cambiar la cantidad se vuelve a cargar el formulario vacío.":
        "Changing the number reloads an empty form.",
    "Cambiar": "Change",
    "Titular de la reserva": "Lead traveller",
    "Nombres": "First names",
    "Apellidos": "Last names",
    "Documento": "ID document",
    "Número de documento": "Document number",
    "País (código)": "Country (code)",
    "Empieza a escribir tu país y elígelo de la lista (Perú = PE).":
        "Start typing your country and pick it from the list (Peru = PE).",
    "Celular o WhatsApp": "Mobile or WhatsApp",
    "Celular peruano de 9 dígitos o con código de país (+33…).":
        "9-digit Peruvian mobile, or with your country code (+33…).",
    "Correo": "Email",
    "Deja al menos un teléfono o un correo.": "Leave at least a phone number or an email.",
    "Yo también viajo": "I am travelling too",
    "Tu tipo de pasajero": "Your passenger type",
    "Si viajas, elige tu tipo de pasajero (se verifica con tu documento en el muelle).":
        "If you are travelling, choose your passenger type (checked against your ID at the pier).",
    "Tipo de pasajero": "Passenger type",
    "Acompañante": "Companion",
    "Acompañantes": "Companions",
    "Agregar acompañante": "Add a companion",
    "Quitar acompañante": "Remove companion",
    "Pago": "Payment",
    "¿Cómo vas a pagar?": "How will you pay?",
    "En el muelle, antes de subir": "At the pier, before boarding",
    "Con Yape o Plin guardamos tu lugar {minutos} minutos para que reportes el pago. Si pagas en el muelle, tu reserva queda confirmada y pagas antes de subir.":
        "With Yape or Plin we hold your seat for {minutos} minutes so you can report your "
        "payment. If you pay at the pier, your booking is confirmed and you pay before boarding.",
    "Precios por persona en esta fecha": "Prices per person on this date",
    "Confirmar reserva": "Confirm booking",
    "Carné de extranjería": "Peruvian foreigner ID (CE)",
    "Pasaporte": "Passport",
    "DNI": "DNI (Peruvian ID)",
    "— Elige —": "— Choose —",
    "¡Listo! Tu reserva {codigo} quedó registrada.": "Done! Your booking {codigo} has been saved.",
    "Tu reserva {codigo} ya estaba registrada: no se creó otra.":
        "Your booking {codigo} was already saved: no duplicate was created.",
    "Escribe tus nombres.": "Enter your first names.",
    "Escribe tus apellidos.": "Enter your last names.",
    "Escribe tu número de documento.": "Enter your document number.",
    "Elige tu país.": "Choose your country.",
    "Escribe los nombres.": "Enter the first names.",
    "Escribe los apellidos.": "Enter the last names.",
    "Escribe el número de documento.": "Enter the document number.",
    "Elige el país.": "Choose the country.",
    "Elige cómo vas a pagar.": "Choose how you will pay.",

    # --- Mensajes del modelo (reserva) ----------------------------------------------------------
    "Usa solo letras, espacios, apóstrofos o guiones.": "Use only letters, spaces, apostrophes or hyphens.",
    "Elige DNI, CE o pasaporte.": "Choose DNI, CE or passport.",
    "El DNI tiene 8 dígitos.": "A DNI has 8 digits.",
    "El carné de extranjería tiene 9 dígitos.": "A CE has 9 digits.",
    "El pasaporte tiene de 6 a 12 letras o números.": "A passport number has 6 to 12 letters or digits.",
    "Elige un país de la lista (código de 2 letras).": "Choose a country from the list (2-letter code).",
    "Celular peruano de 9 dígitos que empieza en 9, o +código del país.":
        "9-digit Peruvian mobile starting with 9, or +country code.",
    "Escribe un correo válido, por ejemplo nombre@correo.com.": "Enter a valid email, for example name@mail.com.",
    "Deja al menos un teléfono o un correo para avisarte cambios.":
        "Leave at least a phone number or an email so we can tell you about changes.",
    "Elige tu tipo de pasajero.": "Choose your passenger type.",
    "Elige el tipo de pasajero.": "Choose the passenger type.",
    "La reserva necesita al menos un pasajero.": "The booking needs at least one passenger.",
    "Este documento ya está en la reserva.": "This document is already in the booking.",
    "El formulario no es válido. Vuelve a cargar la página.": "The form is not valid. Please reload the page.",
    "Esa salida no existe.": "That departure does not exist.",
    "Uno de los tipos de pasajero no tiene precio para esta salida.":
        "One of the passenger types has no price for this departure.",
    "Se acaban de ocupar los últimos lugares. Elige otra salida.":
        "The last seats have just been taken. Please choose another departure.",
    "Hay muchas reservas al mismo tiempo. Inténtalo de nuevo.":
        "There are many bookings at the same time. Please try again.",
    "Ese documento ya está registrado con otro nombre. Revisa los datos o escribe a la agencia.":
        "That document is registered under another name. Check your details or contact the agency.",
    "No pudimos generar el código de la reserva. Inténtalo de nuevo.":
        "We could not create the booking code. Please try again.",
    "Elige Yape o Plin.": "Choose Yape or Plin.",
    "Escribe el monto pagado, por ejemplo 160.00.": "Enter the amount paid, for example 160.00.",
    "Escribe el número de operación que aparece en tu app (4 a 30 caracteres).":
        "Enter the transaction number shown in your app (4 to 30 characters).",
    "Esa reserva no existe.": "That booking does not exist.",
    "Esta reserva no está esperando un pago (ya venció, se pagó o se paga en el muelle).":
        "This booking is not awaiting a payment (it expired, was paid, or is paid at the pier).",
    "El monto no puede ser mayor que el total de la reserva.": "The amount cannot be more than the booking total.",
    "Ese número de operación ya fue reportado.": "That transaction number has already been reported.",

    # --- Ver la reserva ---------------------------------------------------------------------------
    "Reserva {codigo}": "Booking {codigo}",
    "Por tu privacidad, los datos personales se ven ocultos.": "For your privacy, personal details are hidden.",
    "Identifícate con el documento del titular": "Identify yourself with the lead traveller's document",
    "para verlos completos.": "to see them in full.",
    "Tu salida está suspendida": "Your departure is suspended",
    "por seguridad en el lago": "for safety on the lake",
    "Puedes pasar tu reserva a otra salida de la misma ruta, o pedir la devolución de tu dinero.":
        "You can move your booking to another departure on the same route, or ask for a refund.",
    "Reprogramar o pedir la devolución": "Reschedule or ask for a refund",
    "Identifícate para reprogramar": "Identify yourself to reschedule",
    "Recibimos tu reporte de pago.": "We received your payment report.",
    "La agencia lo está verificando; tu lugar está guardado hasta el {plazo}.":
        "The agency is checking it; your seat is held until {plazo}.",
    "Falta tu pago": "Your payment is pending",
    "Guardamos tu lugar hasta el {plazo}.": "We are holding your seat until {plazo}.",
    "Paga {monto} por {metodo}": "Pay {monto} by {metodo}",
    "al": "to",
    "y luego repórtalo aquí.": "and then report it here.",
    "El plazo para pagar ya pasó y el lugar se liberó. Puedes hacer una reserva nueva.":
        "The payment deadline has passed and the seat was released. You can make a new booking.",
    "¿Cómo te fue en el lago?": "How was your time on the lake?",
    "Cuéntanos tu viaje": "Tell us about your trip",
    "Identifícate para dejar tu opinión": "Identify yourself to leave a review",
    "Tu viaje": "Your trip",
    "Zarpe": "Departure",
    "Vuelve": "Returns",
    "Noche del {fecha}: te recibe la {familia} en {comunidad}.":
        "Night of {fecha}: you will stay with the {familia} in {comunidad}.",
    "Titular": "Lead traveller",
    "Nombre": "Name",
    "Teléfono": "Phone",
    "Pasajeros ({n})": "Passengers ({n})",
    "Tipo": "Type",
    "Total": "Total",
    "Pagado (verificado)": "Paid (verified)",
    "Reportado, por verificar": "Reported, being checked",
    "Pagos": "Payments",
    "operación": "transaction",
    "Ver mi boleto con QR": "See my QR ticket",
    "Ver otras salidas": "See other departures",
    "Guarda tu código {codigo}: con él y el documento del titular puedes volver a ver esta reserva desde \"Mi reserva\".":
        "Keep your code {codigo}: with it and the lead traveller's document you can see this "
        "booking again from \"My booking\".",

    # --- Mi reserva, boleto y pago ----------------------------------------------------------------
    "Escribe el código que recibiste al reservar (TV-XXXX) y el número de documento de quien hizo la reserva.":
        "Enter the code you received when booking (TV-XXXX) and the document number of the "
        "person who made the booking.",
    "Código de reserva": "Booking code",
    "Número de documento del titular": "Lead traveller's document number",
    "Ver mi reserva": "See my booking",
    "Escribe el código de tu reserva.": "Enter your booking code.",
    "El código tiene la forma TV-XXXX.": "The code looks like TV-XXXX.",
    "No encontramos una reserva con ese código y ese documento.":
        "We could not find a booking with that code and document.",
    "Boleto": "Ticket",
    "Volver a la reserva": "Back to the booking",
    "Volver a la reserva {codigo}": "Back to booking {codigo}",
    "Pase de abordar": "Boarding pass",
    "Estado": "Status",
    "Lo lee el guía o el capitán al subir": "The guide or captain scans it when you board",
    "Lo lee el guía o el capitán": "Scanned by the guide or captain",
    "Total {total}": "Total {total}",
    "Preséntate en el muelle 30 minutos antes del zarpe con tu documento.":
        "Be at the pier 30 minutes before departure with your ID document.",
    "Descargar PDF": "Download PDF",
    "Consejo: en las islas la señal es débil. Descarga el PDF o toma una captura antes de salir de Puno.":
        "Tip: the signal is weak on the islands. Download the PDF or take a screenshot before leaving Puno.",
    "Código QR del boleto {codigo}": "QR code for ticket {codigo}",
    "Zarpe: {hora}  ·  {muelle}": "Departure: {hora}  ·  {muelle}",
    "Lancha: {nombre}": "Boat: {nombre}",
    "Total: {total}  ·  Estado: {estado}": "Total: {total}  ·  Status: {estado}",
    "El boleto estará listo cuando la reserva esté confirmada o pagada.":
        "The ticket will be ready when the booking is confirmed or paid.",
    "Reportar pago": "Report payment",
    "Reportar mi pago": "Report my payment",
    "Falta pagar {saldo}. Tienes hasta el {plazo}.": "{saldo} still to pay. You have until {plazo}.",
    "A nombre de": "Account holder",
    "Paga desde tu app y copia aquí el número de operación. La agencia lo verifica y tu reserva pasa a \"Pagada\".":
        "Pay from your app and copy the transaction number here. The agency checks it and your "
        "booking becomes \"Paid\".",
    "Revisa el pago": "Please check the payment",
    "¿Con qué pagaste?": "How did you pay?",
    "Monto pagado (S/)": "Amount paid (S/)",
    "Número de operación": "Transaction number",
    "Lo ves en el comprobante de Yape o Plin.": "You can see it on the Yape or Plin receipt.",
    "Escribe el monto.": "Enter the amount.",
    "Escribe el número de operación.": "Enter the transaction number.",
    "Esta reserva no está esperando un pago.": "This booking is not awaiting a payment.",
    "Ya reportaste el total. La agencia está verificando tu pago.":
        "You have already reported the total. The agency is checking your payment.",
    "Recibimos tu reporte de pago. La agencia lo verificará pronto.":
        "We received your payment report. The agency will check it soon.",

    # --- Reprogramar y devolución (RN-11) -------------------------------------------------------
    "Reprogramar": "Reschedule",
    "Motivo:": "Reason:",
    "La suspensión no es tu culpa: al reprogramar se mantienen tu código, tus pagos y tus precios.":
        "The suspension is not your fault: when you reschedule you keep your code, your payments "
        "and your prices.",
    "Revisa tu elección": "Please check your choice",
    "Pasar a otra salida": "Move to another departure",
    "Nueva salida": "New departure",
    "Salidas de la misma ruta con lugar para tu grupo ({n} personas).":
        "Departures on the same route with room for your group ({n} people).",
    "Pasar mi reserva a esta salida": "Move my booking to this departure",
    "Elige una salida.": "Choose a departure.",
    "alerta en el lago": "lake alert",
    "Por ahora no hay otra salida de esta ruta con lugar para tu grupo. Vuelve a mirar más tarde o pide la devolución.":
        "For now there is no other departure on this route with room for your group. Check "
        "again later or ask for a refund.",
    "Pedir la devolución": "Ask for a refund",
    "La agencia te devolverá {monto} y se comunicará contigo por teléfono o correo.":
        "The agency will refund {monto} and contact you by phone or email.",
    "Todavía no tienes pagos verificados: tu reserva se cancelará sin costo.":
        "You have no verified payments yet: your booking will be cancelled at no cost.",
    "Tu reserva quedará cancelada y tu lugar se liberará.":
        "Your booking will be cancelled and your seat released.",
    "Cancelar mi reserva y pedir la devolución": "Cancel my booking and ask for a refund",
    "Esta reserva no necesita reprogramarse: su salida no está suspendida.":
        "This booking does not need rescheduling: its departure is not suspended.",
    "¡Listo! Tu reserva {codigo} pasó a la nueva salida. Tu código, tus pagos y tu boleto siguen valiendo.":
        "Done! Your booking {codigo} moved to the new departure. Your code, payments and ticket "
        "are still valid.",
    "Tu reserva quedó cancelada. La agencia te devolverá {monto} y se comunicará contigo.":
        "Your booking has been cancelled. The agency will refund {monto} and contact you.",
    "Tu reserva quedó cancelada, sin costo.": "Your booking has been cancelled at no cost.",
    "Esta reserva no se puede reprogramar: su salida no está suspendida o la reserva ya no está activa.":
        "This booking cannot be rescheduled: its departure is not suspended or the booking is no "
        "longer active.",
    "Elige otra salida de la misma ruta que todavía no zarpa.":
        "Choose another departure on the same route that has not left yet.",
    "La devolución se pide cuando la salida está suspendida.":
        "A refund can be requested when the departure is suspended.",

    # --- Reseña (RN-13) -------------------------------------------------------------------------
    "Tu opinión": "Your review",
    "Tu opinión ayuda a otros viajeros y a las comunidades. Se publica después de que la agencia la revisa, sin tu nombre: solo tu país y el mes del viaje.":
        "Your review helps other travellers and the communities. It is published after the agency "
        "checks it, without your name: only your country and the month of the trip.",
    "Revisa tu opinión": "Please check your review",
    "¿Cuántas estrellas le das?": "How many stars would you give it?",
    "★★★★★ Excelente": "★★★★★ Excellent",
    "★★★★ Muy bueno": "★★★★ Very good",
    "★★★ Bueno": "★★★ Good",
    "★★ Regular": "★★ Fair",
    "★ Malo": "★ Poor",
    "Comentario": "Comment",
    "Opcional. No escribas teléfonos ni datos personales.": "Optional. Do not include phone numbers or personal details.",
    "Enviar mi opinión": "Send my review",
    "Elige de 1 a 5 estrellas.": "Choose 1 to 5 stars.",
    "¡Gracias! Tu opinión se publicará cuando la agencia la revise.":
        "Thank you! Your review will be published once the agency has checked it.",
    "Ya dejaste tu opinión sobre este viaje. ¡Gracias!": "You have already reviewed this trip. Thank you!",
    "Solo se opina de un viaje que se hizo (reserva abordada).":
        "Reviews are only for trips that took place (boarded bookings).",
    "Podrás opinar cuando termine tu viaje.": "You can leave a review when your trip is over.",

    # --- Páginas de error -----------------------------------------------------------------------
    "Error {codigo}": "Error {codigo}",
    "Ir al inicio": "Go to the home page",
    "Solicitud no válida": "Invalid request",
    "No pudimos procesar lo que enviaste. Vuelve a intentarlo.": "We could not process what you sent. Please try again.",
    "No tienes permiso": "You do not have permission",
    "Tu usuario no puede ver esta página. Si crees que es un error, habla con el administrador.":
        "Your user cannot see this page. If you think this is a mistake, contact the administrator.",
    "No encontramos la página": "Page not found",
    "La dirección no existe o ya no está disponible.": "The address does not exist or is no longer available.",
    "Acción no permitida": "Action not allowed",
    "Esta dirección no acepta esa acción.": "This address does not accept that action.",
    "Demasiados intentos": "Too many attempts",
    "Hiciste demasiados intentos seguidos. Espera unos minutos y vuelve a intentarlo.":
        "You made too many attempts in a row. Wait a few minutes and try again.",
    "Algo salió mal": "Something went wrong",
    "Tuvimos un problema al atender tu pedido. Ya quedó registrado; vuelve a intentarlo en unos minutos.":
        "We had a problem handling your request. It has been logged; please try again in a few minutes.",
    "El formulario venció": "The form expired",
    "Por seguridad, vuelve a cargar la página y envía el formulario otra vez.":
        "For security, reload the page and send the form again.",
    "No hay conexión con la base de datos": "No connection to the database",
    "El sistema no puede leer sus datos en este momento. Vuelve a intentarlo en unos minutos.":
        "The system cannot read its data right now. Please try again in a few minutes.",

    # --- APIs (v2.2): RENIEC, clima del zarpe, feriados y tipo de cambio ---
    "Buscando el DNI en RENIEC…": "Looking up the DNI in RENIEC…",
    "Encontrado en RENIEC: {nombre}. Revisa que esté bien.":
        "Found in RENIEC: {nombre}. Check that it is right.",
    "No pudimos consultar el DNI: escribe los nombres.": "We could not look up the DNI: type the names.",
    "Con DNI peruano, escribe primero el número: los nombres se completan solos (RENIEC). Revísalos antes de confirmar.":
        "With a Peruvian DNI, type the number first: the names fill in by themselves (RENIEC). "
        "Check them before confirming.",
    "La consulta a RENIEC no está activa: escribe los nombres.":
        "The RENIEC lookup is not available: type the names.",
    "RENIEC no responde ahora: escribe los nombres.": "RENIEC is not answering right now: type the names.",
    "No encontramos ese DNI en RENIEC: revisa el número o escribe los nombres.":
        "We did not find that DNI in RENIEC: check the number or type the names.",
    "En dólares": "In US dollars",
    "En dólares, con el tipo de cambio de SUNAT del {fecha} (S/ {venta} por dólar). Es referencial: se paga en soles.":
        "In US dollars, at the SUNAT exchange rate of {fecha} (S/ {venta} per dollar). For reference only: you pay in soles.",
    "Feriado": "Holiday",
    "Feriado: {nombre}. Suele haber más turistas: reserva con tiempo.":
        "Public holiday: {nombre}. There are usually more visitors: book early.",
    "Ese día es feriado ({nombre}): suele haber más turistas, reserva con tiempo.":
        "That day is a public holiday ({nombre}): there are usually more visitors, book early.",
    "El clima para el zarpe": "Weather at departure time",
    "Viento": "Wind",
    "{viento} km/h, ráfagas de {rafagas} km/h": "{viento} km/h, gusts of {rafagas} km/h",
    "Probabilidad de lluvia": "Chance of rain",
    "Sol": "Sun",
    "sale a las {amanecer} y se pone a las {atardecer}": "rises at {amanecer} and sets at {atardecer}",
    "Se espera viento fuerte. Si SENAMHI o la Capitanía dan una alerta, la salida se suspende y podrás reprogramar o pedir la devolución.":
        "Strong wind is expected. If SENAMHI or the Harbour Master issue an alert, the trip is suspended "
        "and you can rebook or ask for a refund.",
    "Pronóstico para la bahía de Puno a las {hora}, de": "Forecast for the bay of Puno at {hora}, from",
    "Es una referencia: la salida la confirman las alertas oficiales.":
        "For reference only: official alerts confirm the trip.",
    # El cielo (códigos WMO de Open-Meteo, servicios/clima.py)
    "Despejado": "Clear sky",
    "Mayormente despejado": "Mainly clear",
    "Parcialmente nublado": "Partly cloudy",
    "Nublado": "Overcast",
    "Niebla": "Fog",
    "Llovizna": "Drizzle",
    "Llovizna helada": "Freezing drizzle",
    "Lluvia débil": "Light rain",
    "Lluvia": "Rain",
    "Lluvia fuerte": "Heavy rain",
    "Lluvia helada": "Freezing rain",
    "Nieve": "Snow",
    "Nieve fuerte": "Heavy snow",
    "Granizo menudo": "Snow grains",
    "Chubascos": "Rain showers",
    "Chubascos fuertes": "Heavy showers",
    "Chubascos de nieve": "Snow showers",
    "Tormenta eléctrica": "Thunderstorm",
    "Tormenta con granizo": "Thunderstorm with hail",
    "Sin dato del cielo": "No sky data",

    # --- Portada con foto, buscador y servicios (v2.3) ---
    "Puno · Lago Titicaca · 3 812 m": "Puno · Lake Titicaca · 3,812 m",
    "Busca tu salida": "Find your trip",
    "¿Qué día?": "Which day?",
    "Buscar salidas": "Search trips",
    "Viaja tranquilo": "Travel with peace of mind",
    "Capitán con licencia": "Licensed captain",
    "Cada salida lleva un capitán con licencia de navegación y la lista de pasajeros para la Capitanía.":
        "Every trip has a captain with a navigation licence and a passenger list for the Harbour Master.",
    "Noche con una familia": "A night with a family",
    "Las familias anfitrionas se turnan, para que todas reciban visitantes.":
        "Host families take turns, so that all of them receive visitors.",
    "Paga como prefieras": "Pay your way",
    "Yape, Plin o en el muelle, antes de subir a la lancha.": "Yape, Plin or at the dock before boarding.",
    "Clima y alertas al día": "Up-to-date weather and alerts",
    "Pronóstico a la hora del zarpe y alertas de SENAMHI y de la Capitanía.":
        "Forecast for departure time and alerts from SENAMHI and the Harbour Master.",
    "Boleto con QR": "Ticket with QR code",
    "Tu código y tu boleto en el celular: no hace falta imprimir.":
        "Your code and ticket on your phone: no need to print.",
    "En español e inglés": "In Spanish and English",
    "Toda la reserva en tu idioma, desde el celular y aunque la señal sea débil.":
        "The whole booking in your language, from your phone, even with a weak signal.",

    # --- Rutas como tarjetas (v2.4) ---
    "por persona": "per person",
    "Ver salidas": "See trips",

    # --- Galería (v2.5) ---
    "Galería": "Gallery",
    "Galería del lago": "Lake gallery",
    "Las islas y comunidades que visitan nuestras rutas. Toca una foto para verla en grande.":
        "The islands and communities our routes visit. Tap a photo to see it larger.",
    "Filtrar por idioma": "Filter by language",
    "Todas": "All",
    "Ver la comunidad": "See the community",
    "Anterior": "Previous",
    "Siguiente": "Next",
    "Cerrar": "Close",
    "Todavía no hay fotos de estas comunidades.": "There are no photos of these communities yet.",
    "Fotos de Wikimedia Commons, con el nombre de su autor y su licencia.":
        "Photos from Wikimedia Commons, with their author's name and licence.",
    "Ver la galería de fotos →": "See the photo gallery →",

    # --- Contacto (v2.6) ---
    "Contacto": "Contact",
    "¿Dudas sobre una salida, una reserva o un viaje en grupo? Escríbenos y te respondemos.":
        "Questions about a trip, a booking or travelling as a group? Write to us and we will answer.",
    "Atención": "Customer service",
    "Escríbenos por WhatsApp": "Message us on WhatsApp",
    "Dónde zarpamos": "Where we depart from",
    "Ver en el mapa": "See on the map",
    "Horario de atención": "Opening hours",
    "¿Ya reservaste?": "Already booked?",
    "Mira tu reserva con tu código": "See your booking with your code",
    "Escríbenos": "Write to us",
    "Deja al menos un correo o un celular para responderte.":
        "Leave at least an email or a mobile number so we can answer you.",
    "Usamos tus datos solo para responderte.": "We only use your details to answer you.",
    "¡Gracias! Recibimos tu mensaje y te responderemos pronto.":
        "Thank you! We received your message and will answer you soon.",
    "No pudimos enviar tu mensaje ahora. Escríbenos por WhatsApp o inténtalo en unos minutos.":
        "We could not send your message right now. Message us on WhatsApp or try again in a few minutes.",
    "Hola, quiero información sobre las salidas al lago.": "Hello, I would like information about the lake trips.",
    "Tu nombre": "Your name",
    "Sobre qué es": "What it is about",
    "Tu mensaje": "Your message",
    "Deja este campo vacío": "Leave this field empty",
    "Enviar mensaje": "Send message",
    "Información de las salidas": "Information about the trips",
    "Una reserva que ya hice": "A booking I already made",
    "Viaje en grupo o con un colegio": "Group or school trip",
    "Otro tema": "Something else",
    "Escribe tu nombre.": "Write your name.",
    "Escribe tu mensaje.": "Write your message.",
    "Escribe tu nombre con letras.": "Write your name using letters.",
    "Deja un correo o un celular para responderte.": "Leave an email or a mobile number so we can answer you.",
    "Elige sobre qué es tu mensaje.": "Choose what your message is about.",
    "Escribe entre 10 y 1500 caracteres.": "Write between 10 and 1500 characters.",

    # --- Pie de página y páginas legales (v2.7) ---
    "Turismo comunitario en el lago Titicaca: salidas en lancha y noches con familias anfitrionas.":
        "Community tourism on Lake Titicaca: boat trips and nights with host families.",
    "Explora": "Explore",
    "Yape, Plin o efectivo en el muelle. Precios en soles, por persona.":
        "Yape, Plin or cash at the dock. Prices in soles, per person.",
    "Privacidad": "Privacy",
    "Condiciones": "Terms",
    "Política de privacidad": "Privacy policy",
    "Condiciones del servicio": "Terms of service",
    "Este texto solo está en español.": "This text is only available in Spanish.",

    # --- Libro de reclamaciones, experiencias y grupos (v2.8) ---
    "Libro de reclamaciones": "Complaints book",
    "Este formulario está en español, como el libro de reclamaciones del Perú.":
        "This form is in Spanish, like the official Peruvian complaints book.",
    "Constancia de tu hoja de reclamación": "Your complaint receipt",
    "Listo: tu hoja quedó registrada con el N.º {numero}.": "Done: your complaint was registered as No. {numero}.",
    "Experiencias": "Experiences",
    "Experiencias en el lago": "Experiences on the lake",
    "Qué puedes vivir en cada comunidad, según las rutas que paran allí y lo que ofrecen sus familias anfitrionas.":
        "What you can do in each community, based on the routes that stop there and what its host families offer.",
    "Filtrar por experiencia": "Filter by experience",
    "Comida casera": "Home-cooked meals",
    "Visita de {duracion}": "{duracion} visit",
    "Noche con una familia anfitriona": "A night with a host family",
    "Ninguna comunidad ofrece todavía esa experiencia.": "No community offers that experience yet.",
    "¿Vienes en grupo?": "Coming as a group?",
    "Colegios, universidades y empresas: te armamos la salida y te enviamos la cotización.":
        "Schools, universities and companies: we arrange the trip and send you a quote.",
    "Pedir cotización para grupos": "Ask for a group quote",
    "Ver experiencias": "See experiences",
    "Viajes en grupo": "Group trips",
    "Colegios, universidades, empresas o familias grandes: cuéntanos cuántos son y cuándo quieren venir, y te enviamos la cotización.":
        "Schools, universities, companies or large families: tell us how many you are and when you want to come, and we will send you a quote.",
    "La salida a tu medida": "A trip made for you",
    "Eliges la ruta y la fecha; la agencia programa la salida y te confirma los lugares.":
        "You choose the route and the date; the agency schedules the trip and confirms your seats.",
    "Precio claro": "Clear prices",
    "La tarifa por persona de cada ruta: abajo ves la referencia y la cotización final te llega por correo.":
        "The fare per person of each route: see the reference below; the final quote arrives by email.",
    "Noche en familias": "Nights with families",
    "En las rutas con noche, el grupo se reparte entre familias anfitrionas, por turnos.":
        "On routes with an overnight stay, the group is shared among host families, taking turns.",
    "Precios de referencia por persona": "Reference prices per person",
    "con noche": "with overnight stay",
    "Pide tu cotización": "Ask for your quote",
    "¡Gracias! Te enviaremos la cotización para {personas} personas. Precio referencial: desde {total}.":
        "Thank you! We will send you the quote for {personas} people. Reference price: from {total}.",
    "¡Gracias! Te enviaremos la cotización para {personas} personas.":
        "Thank you! We will send you the quote for {personas} people.",
    "No pudimos enviar tu pedido ahora. Escríbenos por WhatsApp o inténtalo en unos minutos.":
        "We could not send your request right now. Message us on WhatsApp or try again in a few minutes.",
    "Tipo de grupo": "Type of group",
    "Colegio": "School",
    "Universidad o instituto": "University or institute",
    "Empresa o institución": "Company or institution",
    "Familia o amigos": "Family or friends",
    "Otro grupo": "Another group",
    "Nombre del colegio, empresa o grupo (opcional)": "Name of the school, company or group (optional)",
    "¿Cuántas personas?": "How many people?",
    "Fecha que prefieren": "Preferred date",
    "Algo más que debamos saber (opcional)": "Anything else we should know (optional)",
    "Pedir cotización": "Ask for a quote",
    "Escribe cuántas personas son.": "Write how many people you are.",
    "Elige la fecha.": "Choose the date.",
    "Elige qué tipo de grupo es.": "Choose the type of group.",
    "Escribe cuántas personas son (de 2 a 300).": "Write how many people you are (2 to 300).",
    "Elige una fecha desde hoy y dentro del próximo año.": "Choose a date from today and within the next year.",
    "Elige una ruta de la lista.": "Choose a route from the list.",
    # --- Productos y artesanías (v2.9) ---
    "Productos": "Products",
    "Productos y artesanías": "Products and crafts",
    "Lo que hacen y venden las familias de las islas y la agencia, con su precio, sus características y dónde encontrarlo.":
        "What the island families and the agency make and sell, with its price, its features and where to find it.",
    "Las descripciones las escriben la agencia y los residentes, en español.":
        "Descriptions are written by the agency and the residents, in Spanish.",
    "Filtrar por lugar": "Filter by place",
    "Todos los lugares": "All places",
    "Filtrar por tipo": "Filter by type",
    "Todo": "Everything",
    "Tejidos y bordados": "Weaving and embroidery",
    "Tallados y artesanías": "Carvings and crafts",
    "Productos del campo": "Farm products",
    "Recuerdos": "Souvenirs",
    "Dónde está": "Where it is",
    "Lo ofrece": "Sold by",
    "residente de {comunidad}": "resident of {comunidad}",
    "La agencia Titicaca Vivo": "The Titicaca Vivo agency",
    "No hay productos con ese filtro todavía.": "There are no products with that filter yet.",
    "¿Vives en una isla y quieres vender aquí?": "Do you live on an island and want to sell here?",
    "La agencia te crea una cuenta de residente: publicas tus artesanías y productos con su precio y se ven aquí al instante.":
        "The agency creates a resident account for you: you post your crafts and products with their price, and they show up here right away.",
    "Pedir mi cuenta de residente": "Ask for my resident account",
    "Artesanías y productos de las islas": "Crafts and products from the islands",
    "Los publican las familias de cada comunidad y la agencia: con su precio y dónde encontrarlos.":
        "Posted by the families of each community and by the agency, with their price and where to find them.",
    "Ver todos los productos →": "See all products →",
    "La foto pesa demasiado": "The photo is too large",
    "La foto puede pesar hasta 8 MB. Elige otra o tómala con menos resolución.":
        "The photo can be up to 8 MB. Choose another one or take it at a lower resolution.",
}

# Mensajes con partes variables (números, códigos): se reconocen con un patrón.
PATRONES = [
    (re.compile(r"Solo quedan (\d+) lugar(?:es)? en esta salida\."),
     "Only {0} seat(s) left on this departure."),
    (re.compile(r"Solo quedan (\d+) lugares en esa salida\."),
     "Only {0} seat(s) left on that departure."),
    (re.compile(r"Una reserva lleva como máximo (\d+) pasajeros\."),
     "A booking can have at most {0} passengers."),
    (re.compile(r"El documento (\S+) (\S+) ya tiene un lugar en esta salida\."),
     "Document {0} {1} already has a seat on this departure."),
    (re.compile(r"El documento (\S+) (\S+) ya viaja en esa salida\."),
     "Document {0} {1} is already travelling on that departure."),
    (re.compile(r"No hay una familia anfitriona libre para (\d+) personas? esa noche\. Prueba otra "
                r"fecha, divide el grupo en dos reservas o escribe a la agencia\."),
     "There is no host family free for {0} people that night. Try another date, split the "
     "group into two bookings or contact the agency."),
    (re.compile(r"Máximo (\d+) caracteres\."), "Maximum {0} characters."),
]

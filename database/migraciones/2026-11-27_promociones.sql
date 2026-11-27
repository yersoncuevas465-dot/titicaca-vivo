-- Promociones (27/11/2026): una temporada puede bajar el precio (recargo de −50 a 100 %).
-- Para una base que ya existía (Railway con volumen). Se puede correr las veces que sea:
-- borra la regla vieja si está y pone la nueva.
ALTER TABLE temporada DROP CONSTRAINT IF EXISTS ck_temporada_recargo;
ALTER TABLE temporada ADD CONSTRAINT ck_temporada_recargo CHECK (recargo_porcentaje BETWEEN -50 AND 100);

# Captura de precios supercarros → Postgres

Contenedor que scrapea precios de vehículos **usados** en supercarros.com (pasando su anti-bot con navegador stealth), normaliza a USD y los guarda agregados por marca/modelo/año en Postgres. Alimenta el contexto de viabilidad interno de Abby.

## Qué hace cada corrida

1. Lee `supercarros_pendientes` (modelos que pidieron leads, `capturado=false`) + modelos en `supercarros_precios` con data más vieja que `REFRESH_DIAS`.
2. Para cada marca/modelo: resuelve sus IDs desde `searchvalues.js`, scrapea las páginas de búsqueda de **usados** (`Condition=252`), parsea precio/año/condición, normaliza DOP→USD (tasa automática), agrega (promedio/mediana/min/max/n por año).
3. `UPSERT` en `supercarros_precios` y marca los pendientes como `capturado=true`.

Corre **una vez y termina** → se dispara con un *scheduled job* semanal de easypanel.

## Requisitos previos

- Tablas creadas (ver `../sql/001_supercarros_schema.sql`).
- `DATABASE_URL` apuntando al MISMO Postgres que usa n8n (credencial `Postgres-AUTRAB`). Guardar en variables de entorno del servicio en easypanel (NO en el repo).

## Deploy en easypanel

1. Crear un servicio tipo **App** desde este directorio (o build del `Dockerfile`).
2. Variables de entorno: `DATABASE_URL` (requerida), opcional `REFRESH_DIAS`, `MAX_PAGES`.
3. Configurar **Scheduled job / cron**: semanal (ej. `0 4 * * 1` = lunes 4am). El comando ya es `python run_capture.py`.
4. (Primera vez) ejecutar el job manualmente y revisar logs: deben aparecer líneas `[ok] <marca> <modelo>: N cards -> M filas`.

## Verificación

```sql
SELECT marca, modelo, anio, n_listings, precio_mediana_usd, fecha_captura
FROM supercarros_precios ORDER BY fecha_captura DESC LIMIT 20;
```

## Notas

- Lógica de fetch/parse/FX/agregación validada localmente con datos reales (Toyota Corolla, 2026-06-12).
- Si supercarros cambia su HTML, ajustar `ANCHOR_JS` / `CARD_TXT` en `capture_core.py`.
- Solo captura **usados** (AUTRAB importa usados); el filtro va en la URL (`Condition=252`).

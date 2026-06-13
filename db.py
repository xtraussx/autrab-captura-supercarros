"""Capa Postgres del contenedor de captura (psycopg2). Mismo SQL validado via webhook en dev."""
import os, psycopg2, psycopg2.extras

def conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("Falta DATABASE_URL (ej. postgres://user:pass@host:5432/db)")
    return psycopg2.connect(dsn)

def leer_pendientes(cur):
    cur.execute("SELECT marca, modelo, anio FROM supercarros_pendientes WHERE capturado = false")
    return cur.fetchall()

def upsert_precios(cur, filas):
    if not filas:
        return 0
    sql = (
        "INSERT INTO supercarros_precios "
        "(marca,modelo,anio,condicion,n_listings,precio_min_usd,precio_max_usd,"
        "precio_promedio_usd,precio_mediana_usd,fecha_captura) "
        "VALUES (%(marca)s,%(modelo)s,%(anio)s,%(condicion)s,%(n_listings)s,"
        "%(precio_min_usd)s,%(precio_max_usd)s,%(precio_promedio_usd)s,%(precio_mediana_usd)s,now()) "
        "ON CONFLICT (marca,modelo,anio,condicion) DO UPDATE SET "
        "n_listings=EXCLUDED.n_listings,precio_min_usd=EXCLUDED.precio_min_usd,"
        "precio_max_usd=EXCLUDED.precio_max_usd,precio_promedio_usd=EXCLUDED.precio_promedio_usd,"
        "precio_mediana_usd=EXCLUDED.precio_mediana_usd,fecha_captura=now()"
    )
    psycopg2.extras.execute_batch(cur, sql, filas)
    return len(filas)

def marcar_capturado(cur, marca, modelo):
    cur.execute("UPDATE supercarros_pendientes SET capturado=true "
                "WHERE lower(marca)=lower(%s) AND lower(modelo)=lower(%s)", (marca, modelo))

def modelos_a_refrescar(cur, dias=30):
    """Modelos ya capturados pero con data mas vieja que N dias (para re-scrapear)."""
    cur.execute("SELECT DISTINCT marca, modelo FROM supercarros_precios "
                "WHERE fecha_captura < now() - (%s || ' days')::interval", (dias,))
    return cur.fetchall()

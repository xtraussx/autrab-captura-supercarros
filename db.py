"""Capa Postgres del contenedor de captura (psycopg2). Captura POR MARCA."""
import os, psycopg2, psycopg2.extras

def conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("Falta DATABASE_URL (ej. postgres://user:pass@host:5432/db)")
    return psycopg2.connect(dsn)

def marcas_pendientes(cur):
    """Marcas distintas con algo pendiente de capturar."""
    cur.execute("SELECT DISTINCT lower(marca) FROM supercarros_pendientes WHERE capturado = false")
    return [r[0] for r in cur.fetchall()]

def marcas_a_refrescar(cur, dias=30):
    """Marcas con data mas vieja que N dias."""
    cur.execute("SELECT DISTINCT lower(marca) FROM supercarros_precios "
                "WHERE fecha_captura < now() - (%s || ' days')::interval", (dias,))
    return [r[0] for r in cur.fetchall()]

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

def marcar_marca_capturada(cur, marca):
    cur.execute("UPDATE supercarros_pendientes SET capturado=true WHERE lower(marca)=lower(%s)", (marca,))

"""Orquestador del contenedor de captura (corrida semanal). Captura POR MARCA completa.
Lee marcas pendientes + marcas a refrescar, captura cada una (todos sus modelos), upsert, marca."""
import asyncio, os
from capture_core import capturar_marca, descargar_sv, fx_dop_per_usd, todas_las_marcas
import db

REFRESH_DIAS = int(os.environ.get("REFRESH_DIAS", "30"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "12"))
ALL_BRANDS = os.environ.get("ALL_BRANDS", "1") == "1"  # catalogo completo (recomendado)

def _guardar(filas, marca):
    """Abre conexion FRESCA solo para el upsert (evita timeout por conexion ociosa durante el scraping)."""
    cn = db.conn(); cn.autocommit = False
    try:
        cur = cn.cursor()
        n = db.upsert_precios(cur, filas)
        db.marcar_marca_capturada(cur, marca)
        cn.commit()
        return n
    except Exception:
        cn.rollback(); raise
    finally:
        cn.close()

async def main():
    js = descargar_sv()
    dop = fx_dop_per_usd()
    print(f"[capture] FX 1USD={dop} DOP | refresco>{REFRESH_DIAS}d | max_pages={MAX_PAGES} | all_brands={ALL_BRANDS}", flush=True)

    if ALL_BRANDS:
        marcas = todas_las_marcas(js)
        print(f"[capture] CATALOGO COMPLETO: {len(marcas)} marcas", flush=True)
    else:
        cn = db.conn(); cur = cn.cursor()
        try:
            pend = db.marcas_pendientes(cur)
            refr = db.marcas_a_refrescar(cur, REFRESH_DIAS)
        finally:
            cn.close()
        marcas, seen = [], set()
        for m in list(pend) + list(refr):
            if m in seen:
                continue
            seen.add(m); marcas.append(m)
        print(f"[capture] marcas objetivo: {len(marcas)} (pendientes={len(pend)}, refrescar={len(refr)})", flush=True)

    for ma in marcas:
        try:
            res = await capturar_marca(ma, max_pages=MAX_PAGES, js=js, dop=dop)  # scraping SIN conexion DB abierta
            if not res["ok"]:
                print(f"  [skip] {ma}: {res['error']}", flush=True)
                continue
            if not res["filas"]:
                print(f"  [ok] {ma}: {res['n_cards']} cards -> 0 filas", flush=True)
                continue
            n = _guardar(res["filas"], ma)
            print(f"  [ok] {ma}: {res['n_cards']} cards -> {n} filas (modelo-anio)", flush=True)
        except Exception as e:
            print(f"  [error] {ma}: {type(e).__name__}: {e}", flush=True)

    print("[capture] fin", flush=True)

def _run_once():
    asyncio.run(main())

if __name__ == "__main__":
    import time
    if os.environ.get("RUN_LOOP", "0") == "1":
        intervalo = int(os.environ.get("INTERVAL_DAYS", "7")) * 86400
        while True:
            try:
                _run_once()
            except Exception as e:
                print(f"[capture] error en corrida: {type(e).__name__}: {e}", flush=True)
            print(f"[capture] durmiendo {intervalo//86400} dia(s)...", flush=True)
            time.sleep(intervalo)
    else:
        _run_once()

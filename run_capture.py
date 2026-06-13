"""Orquestador del contenedor de captura (corrida semanal).
Lee la cola de pendientes + modelos a refrescar, captura cada uno, upsert a Postgres, marca capturado.
"""
import asyncio, os, sys
from capture_core import capturar, descargar_sv, fx_dop_per_usd
import db

REFRESH_DIAS = int(os.environ.get("REFRESH_DIAS", "30"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "10"))

async def main():
    js = descargar_sv()
    dop = fx_dop_per_usd()
    print(f"[capture] FX 1USD={dop} DOP | refresco>{REFRESH_DIAS}d | max_pages={MAX_PAGES}", flush=True)
    cn = db.conn(); cn.autocommit = False
    cur = cn.cursor()

    pendientes = db.leer_pendientes(cur)
    refrescar = db.modelos_a_refrescar(cur, REFRESH_DIAS)
    objetivos = []
    seen = set()
    for (ma, mo, *_rest) in list(pendientes) + list(refrescar):
        key = (ma.lower(), mo.lower())
        if key in seen:
            continue
        seen.add(key); objetivos.append((ma, mo))
    print(f"[capture] objetivos: {len(objetivos)} (pendientes={len(pendientes)}, refrescar={len(refrescar)})", flush=True)

    for ma, mo in objetivos:
        try:
            res = await capturar(ma, mo, max_pages=MAX_PAGES, js=js, dop=dop)
            if not res["ok"]:
                print(f"  [skip] {ma} {mo}: {res['error']}", flush=True)
                continue
            n = db.upsert_precios(cur, res["filas"])
            db.marcar_capturado(cur, ma, mo)
            cn.commit()
            print(f"  [ok] {ma} {mo}: {res['n_cards']} cards -> {n} filas (anios)", flush=True)
        except Exception as e:
            cn.rollback()
            print(f"  [error] {ma} {mo}: {type(e).__name__}: {e}", flush=True)

    cur.close(); cn.close()
    print("[capture] fin", flush=True)

def _run_once():
    asyncio.run(main())

if __name__ == "__main__":
    import time
    # RUN_LOOP=1 -> demonio: corre y duerme INTERVAL_DAYS (default 7). Si no, corre una vez y termina.
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

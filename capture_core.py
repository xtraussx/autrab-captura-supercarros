"""Nucleo de captura supercarros: fetch (usados, paginado) -> parse -> FX -> agrega.
Logica VALIDADA localmente con datos reales (2026-06-12)."""
import asyncio, re, statistics, urllib.request, json
from patchright.async_api import async_playwright
from sv_resolver import descargar_sv, resolver, url_busqueda

CARD_TXT = re.compile(r'(US\$|RD\$)\s*([\d.,]+)\s+(.*)', re.S)

ANCHOR_JS = r"""
() => {
  const re=/\/[a-z0-9\-]+\/\d{4,}\/?$/i; const out=[]; const seen=new Set();
  document.querySelectorAll('a[href]').forEach(a=>{
    const path=new URL(a.href,location.href).pathname;
    if(!re.test(path)) return; if(seen.has(a.href)) return; seen.add(a.href);
    out.push((a.innerText||a.textContent||'').replace(/\s+/g,' ').trim());
  });
  const total=document.querySelector('#UpperCounter2')?.innerText||'';
  return {total, cards:out};
}
"""

def fx_dop_per_usd(default=60.0):
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/USD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
        rate = data.get("rates", {}).get("DOP")
        if rate and rate > 1:
            return float(rate)
    except Exception as e:
        print("  [FX] fallo API, uso default:", e)
    return default

def parse_card(txt):
    m = CARD_TXT.match(txt.strip())
    if not m:
        return None
    cur, num, resto = m.groups()
    moneda = "USD" if cur == "US$" else "DOP"
    monto = int(re.sub(r"[^0-9]", "", num) or 0)
    cond = "usado" if re.search(r"\busado\b", resto, re.I) else ("nuevo" if re.search(r"\bnuevo\b", resto, re.I) else None)
    yrs = re.findall(r"\b(19\d\d|20[0-3]\d)\b", resto)
    anio = int(yrs[0]) if yrs else None
    return {"moneda": moneda, "monto": monto, "condicion": cond, "anio": anio}

def a_usd(monto, moneda, dop_per_usd):
    if monto <= 0:
        return None
    return float(monto) if moneda == "USD" else round(monto / dop_per_usd, 2)

async def fetch_listings(brand_id, model_id, condicion="usado", max_pages=10):
    cards = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(locale="es-DO", viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        for pg in range(max_pages):
            url = url_busqueda(brand_id, model_id, condicion, page=pg)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            data = await page.evaluate(ANCHOR_JS)
            cards.extend(data["cards"])
            if len(data["cards"]) < 24:
                break
        await browser.close()
    return cards

def agregar(parsed, marca, modelo):
    grupos = {}
    for r in parsed:
        if not r or r["precio_usd"] is None or r["anio"] is None or r["condicion"] != "usado":
            continue
        grupos.setdefault((marca.lower(), modelo.lower(), r["anio"], "usado"), []).append(r["precio_usd"])
    filas = []
    for (ma, mo, an, co), precios in sorted(grupos.items()):
        filas.append({"marca": ma, "modelo": mo, "anio": an, "condicion": co,
                      "n_listings": len(precios),
                      "precio_min_usd": round(min(precios), 2),
                      "precio_max_usd": round(max(precios), 2),
                      "precio_promedio_usd": round(statistics.mean(precios), 2),
                      "precio_mediana_usd": round(statistics.median(precios), 2)})
    return filas

async def capturar(marca, modelo, max_pages=10, js=None, dop=None):
    js = js or descargar_sv()
    r = resolver(marca, modelo, js)
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "filas": []}
    dop = dop or fx_dop_per_usd()
    cards = await fetch_listings(r["brand_id"], r["model_id"], "usado", max_pages)
    parsed = []
    for c in cards:
        pc = parse_card(c)
        if pc:
            pc["precio_usd"] = a_usd(pc["monto"], pc["moneda"], dop)
            parsed.append(pc)
    return {"ok": True, "error": None, "filas": agregar(parsed, marca, modelo),
            "brand_id": r["brand_id"], "model_id": r["model_id"], "fx": dop, "n_cards": len(cards)}

"""Nucleo de captura supercarros POR MARCA + modelo extraido del titulo (coarse).
Maneja marcas agrupadas (BMW X5 bajo 'x', etc.). Logica validada con datos reales (2026-06-13)."""
import asyncio, re, statistics, urllib.request, json
from patchright.async_api import async_playwright
from sv_resolver import descargar_sv, parse_brands

CARD_TXT = re.compile(r'(US\$|RD\$)\s*([\d.,]+)\s+(.*)', re.S)

ANCHOR_JS = r"""
() => {
  const re=/\/[a-z0-9\-]+\/\d{4,}\/?$/i; const out=[]; const seen=new Set();
  document.querySelectorAll('a[href]').forEach(a=>{
    const path=new URL(a.href,location.href).pathname;
    if(!re.test(path)) return; if(seen.has(a.href)) return; seen.add(a.href);
    out.push((a.innerText||a.textContent||'').replace(/\s+/g,' ').trim());
  });
  return out;
}
"""

def fx_dop_per_usd(default=60.0):
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/USD", headers={"User-Agent": "Mozilla/5.0"})
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

def modelo_coarse(titulo, marca):
    """Extrae el modelo del titulo: 'BMW X 5 M Package' -> 'x5', 'Toyota Corolla LE' -> 'corolla'."""
    t = re.sub(r'^(US\$|RD\$)\s*[\d.,]+\s*', '', titulo)
    t = re.split(r'\b(19\d\d|20\d\d)\b', t)[0].strip()
    m = marca.strip().lower()
    if t.lower().startswith(m):
        t = t[len(m):].strip()
    toks = t.split()
    if not toks:
        return ''
    if len(toks) >= 2 and re.fullmatch(r'[A-Za-z]{1,2}', toks[0]) and re.match(r'^\d', toks[1]):
        return (toks[0] + toks[1]).lower()
    return re.sub(r'[^a-z0-9]', '', toks[0].lower())

async def fetch_brand(brand_id, max_pages=12):
    cards = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(locale="es-DO", viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        for pg in range(max_pages):
            url = f"https://www.supercarros.com/buscar/?do=1&ObjectType=1&Brand={brand_id}&Condition=252"
            if pg:
                url += f"&PagingPageSkip={pg}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(3000)
                c = await page.evaluate(ANCHOR_JS)
            except Exception as e:
                # una pagina lenta/caida no debe tumbar la marca: usar lo que se haya logrado
                print(f"    [warn] brand={brand_id} pag {pg}: {type(e).__name__}", flush=True)
                break
            cards.extend(c)
            if len(c) < 24:
                break
        await browser.close()
    return cards

def agregar(cards, marca, dop):
    grupos = {}
    for txt in cards:
        pc = parse_card(txt)
        if not pc or pc["anio"] is None or pc["condicion"] != "usado":
            continue
        usd = a_usd(pc["monto"], pc["moneda"], dop)
        if usd is None:
            continue
        mod = modelo_coarse(txt, marca)
        if not mod:
            continue
        grupos.setdefault((marca.lower(), mod, pc["anio"], "usado"), []).append(usd)
    filas = []
    for (ma, mo, an, co), precios in sorted(grupos.items()):
        filas.append({"marca": ma, "modelo": mo, "anio": an, "condicion": co,
                      "n_listings": len(precios),
                      "precio_min_usd": round(min(precios), 2),
                      "precio_max_usd": round(max(precios), 2),
                      "precio_promedio_usd": round(statistics.mean(precios), 2),
                      "precio_mediana_usd": round(statistics.median(precios), 2)})
    return filas

def todas_las_marcas(js=None):
    """Lista de marcas 'reales' (nombre alfabetico, len>=2) del catalogo supercarros."""
    js = js or descargar_sv()
    b = parse_brands(js)
    return sorted(k for k in b if re.search(r'[a-z]', k) and len(k) >= 2)

async def capturar_marca(marca, max_pages=12, js=None, dop=None):
    """Captura TODA la marca (todos sus modelos) y agrega por (marca, modelo_coarse, anio)."""
    js = js or descargar_sv()
    brands = parse_brands(js)
    bid = brands.get(marca.strip().lower())
    if not bid:
        return {"ok": False, "error": f"marca '{marca}' no encontrada", "filas": []}
    dop = dop or fx_dop_per_usd()
    cards = await fetch_brand(bid, max_pages)
    return {"ok": True, "error": None, "filas": agregar(cards, marca, dop),
            "brand_id": bid, "fx": dop, "n_cards": len(cards)}

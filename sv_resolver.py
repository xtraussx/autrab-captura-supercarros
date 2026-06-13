"""Resuelve nombre de marca/modelo -> IDs usando searchvalues.js de supercarros."""
import re, urllib.request

SV_URL = "https://www.supercarros.com/assets/js/searchvalues.js"

def descargar_sv():
    req = urllib.request.Request(SV_URL, headers={"User-Agent": "Mozilla/5.0 Chrome/148"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

def _norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()

def parse_brands(js):
    # SearchBrands = ["838|212|...","36|Acura|1|...", ...]
    m = re.search(r'SearchBrands\s*=\s*\[(.*?)\];', js, re.S)
    out = {}
    for item in re.findall(r'"([^"]+)"', m.group(1)):
        parts = item.split("|")
        if len(parts) >= 2 and parts[0].isdigit():
            out[_norm(parts[1])] = int(parts[0])
    return out

def parse_models(js):
    # SearchModels[26] = ["122|Corolla|...","..."]; indexado por brandId
    out = {}  # brandId -> {modelNameNorm: modelId}
    for bm in re.finditer(r'SearchModels\[(\d+)\]\s*=\s*\[(.*?)\];', js, re.S):
        bid = int(bm.group(1)); d = {}
        for item in re.findall(r'"([^"]+)"', bm.group(2)):
            parts = item.split("|")
            if len(parts) >= 2 and parts[0].isdigit():
                d[_norm(parts[1])] = int(parts[0])
        out[bid] = d
    return out

def resolver(marca, modelo, js=None):
    js = js or descargar_sv()
    brands = parse_brands(js)
    models = parse_models(js)
    bid = brands.get(_norm(marca))
    if bid is None:
        return {"ok": False, "error": f"marca '{marca}' no encontrada", "brand_id": None, "model_id": None}
    mid = models.get(bid, {}).get(_norm(modelo))
    return {"ok": mid is not None, "brand_id": bid, "model_id": mid,
            "error": None if mid is not None else f"modelo '{modelo}' no encontrado en marca '{marca}'"}

CONDICION = {"usado": 252, "nuevo": 251}

def url_busqueda(brand_id, model_id, condicion="usado", page=0):
    base = f"https://www.supercarros.com/buscar/?do=1&ObjectType=1&Brand={brand_id}&Model={model_id}"
    if condicion in CONDICION:
        base += f"&Condition={CONDICION[condicion]}"
    if page:
        base += f"&PagingPageSkip={page}"
    return base

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    js = descargar_sv()
    for ma, mo in [("Toyota","Corolla"), ("Honda","Civic"), ("Toyota","RAV4"), ("Kia","Sportage"), ("Marca X","Modelo Y")]:
        r = resolver(ma, mo, js)
        print(f"{ma} {mo}: {r}")
        if r["ok"]:
            print("   URL usado:", url_busqueda(r["brand_id"], r["model_id"], "usado"))

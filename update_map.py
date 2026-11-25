#!/usr/bin/env python3
"""
Lee todas las bases de datos de Notion compartidas con tu integración,
recoge el campo «Lugar» (o el nombre que configures), lo geocodifica
y escribe docs/data.json. docs/index.html dibuja el mapa a partir de ese archivo.

Solo usa la librería estándar de Python (no hay que instalar nada).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
PROPERTY_NAME = os.environ.get("PROPERTY_NAME", "Lugar")
GEOCODER_CONTACT = os.environ.get("GEOCODER_CONTACT", "notion-map-personal")
NOTION_VERSION = "2025-09-03"

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "geocache.json"
DATA_FILE = ROOT / "docs" / "data.json"


# ---------------------------------------------------------------- Notion API
def notion(method, path, body=None):
    url = "https://api.notion.com/v1" + path
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(6):
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After", 2)))
                continue
            if e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Notion {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError("Notion: demasiados reintentos")


def paginate(path, body):
    cursor = None
    while True:
        b = dict(body, page_size=100)
        if cursor:
            b["start_cursor"] = cursor
        res = notion("POST", path, b)
        yield from res.get("results", [])
        if not res.get("has_more"):
            return
        cursor = res.get("next_cursor")


def all_data_sources():
    yield from paginate(
        "/search", {"filter": {"property": "object", "value": "data_source"}}
    )


def query_pages(data_source_id):
    yield from paginate(f"/data_sources/{data_source_id}/query", {})


# ------------------------------------------------------ lectura del campo
def plain(rich):
    return "".join(r.get("plain_text", "") for r in (rich or []))


def split_text(text):
    return [s.strip() for s in re.split(r"[\n;]+", text) if s.strip()]


def extract_places(prop):
    """Devuelve una lista de {'label', 'coords'?, 'query'?} según el tipo de campo."""
    t = prop.get("type")
    v = prop.get(t)
    out = []
    if not v:
        return out

    if t == "place":
        lat = v.get("lat", v.get("latitude"))
        lon = v.get("lon", v.get("lng", v.get("longitude")))
        label = v.get("name") or v.get("address") or ""
        if lat is not None and lon is not None:
            out.append({"label": label, "coords": [float(lat), float(lon)]})
        else:
            q = ", ".join(x for x in (v.get("name"), v.get("address")) if x)
            if q:
                out.append({"label": label or q, "query": q})
    elif t in ("title", "rich_text"):
        for s in split_text(plain(v)):
            out.append({"label": s, "query": s})
    elif t == "select":
        out.append({"label": v.get("name", ""), "query": v.get("name", "")})
    elif t == "multi_select":
        for o in v:
            out.append({"label": o.get("name", ""), "query": o.get("name", "")})
    elif t == "formula" and v.get("type") == "string" and v.get("string"):
        for s in split_text(v["string"]):
            out.append({"label": s, "query": s})
    return [p for p in out if p.get("coords") or p.get("query")]


# ------------------------------------------------------------ geocodificación
def geocode(query, cache):
    """OpenStreetMap Nominatim. Máx. 1 petición/segundo; los resultados se cachean."""
    key = query.strip().lower()
    if key in cache:
        return cache[key]
    time.sleep(1.1)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1}
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": f"notion-map-sync/1.0 ({GEOCODER_CONTACT})"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.load(r)
    except Exception as e:  # error de red: no se cachea, se reintenta la próxima vez
        print(f"  ! error geocodificando «{query}»: {e}")
        return None
    cache[key] = [float(res[0]["lat"]), float(res[0]["lon"])] if res else None
    return cache[key]


# ------------------------------------------------------------------- main
def main():
    if not NOTION_TOKEN:
        sys.exit("Falta la variable de entorno NOTION_TOKEN")

    cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    cache_before = json.dumps(cache, sort_keys=True)

    points, unresolved = [], []
    with_field, without_field = [], []

    for ds in all_data_sources():
        props = ds.get("properties", {})
        field = next(
            (k for k in props if k.strip().lower() == PROPERTY_NAME.strip().lower()),
            None,
        )
        ds_title = plain(ds.get("title")) or "Sin título"
        if not field:
            without_field.append(ds_title)
            continue
        with_field.append(ds_title)
        title_prop = next((k for k, p in props.items() if p["type"] == "title"), None)
        print(f"→ {ds_title}")

        for page in query_pages(ds["id"]):
            pprops = page.get("properties", {})
            page_title = plain(pprops.get(title_prop, {}).get("title")) or "Sin título"
            for place in extract_places(pprops.get(field, {})):
                coords = place.get("coords") or geocode(place["query"], cache)
                if not coords:
                    unresolved.append(f"{ds_title} · {page_title} · {place['label']}")
                    continue
                points.append(
                    {
                        "db": ds_title,
                        "title": page_title,
                        "place": place["label"],
                        "lat": round(coords[0], 6),
                        "lon": round(coords[1], 6),
                        "url": page.get("url", ""),
                    }
                )

    points.sort(key=lambda p: (p["db"], p["title"], p["place"]))
    print(f"\nBases con «{PROPERTY_NAME}»: {len(with_field)}  |  sin el campo: {len(without_field)}")
    if without_field:
        print("  Sin el campo (ignoradas):", ", ".join(without_field))
    print(f"Lugares en el mapa: {len(points)}  |  sin localizar: {len(unresolved)}")
    for u in unresolved:
        print("  - no localizado:", u)
    if not with_field:
        print(
            "\nAVISO: no se encontró ninguna base con ese campo. ¿Compartiste las páginas "
            "con la integración (⋯ → Conexiones)? ¿El campo se llama exactamente así?"
        )

    if json.dumps(cache, sort_keys=True) != cache_before:
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True))

    # Solo se reescribe data.json si hay cambios reales (evita commits inútiles)
    old = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {}
    if old.get("points") != points or old.get("unresolved") != len(unresolved):
        DATA_FILE.write_text(
            json.dumps(
                {
                    "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                    "unresolved": len(unresolved),
                    "points": points,
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        print("data.json actualizado")
    else:
        print("Sin cambios")


if __name__ == "__main__":
    main()

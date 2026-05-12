#!/usr/bin/env python3
"""
Test: lista formularios del sitio Webflow, filtra por nombre
y prueba distintos endpoints para obtener submissions.
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.environ["WEBFLOW_API_TOKEN"]
SITE_ID = os.environ["WEBFLOW_SITE_ID"]
BASE    = "https://api.webflow.com/v2"

TARGET_FORMS = {
    "form-utm",
    "form-utm-custodia",
    "form-utm-home",
    "form-utm-lp-rutas-alto-riesgo",
}

def get(path: str, params: dict = None) -> requests.Response:
    return requests.get(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
        params=params or {},
    )

def dump(label: str, r: requests.Response):
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"  Status: {r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(r.text)
    print(f"{'─'*60}")


# ── 1. Listar todos los formularios ────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"GET /sites/{SITE_ID}/forms")
print(f"{'='*60}")

r = get(f"/sites/{SITE_ID}/forms")
dump("Respuesta raw completa de /forms", r)

if r.status_code != 200:
    print("\nNo se pudo obtener formularios. Abortando.")
    raise SystemExit(1)

all_forms = r.json().get("forms", [])
print(f"\nTotal formularios: {len(all_forms)}")
print("Nombres encontrados:")
for f in all_forms:
    print(f"  - '{f.get('displayName')}' (id={f.get('id')})")

# ── 2. Filtrar por nombre ──────────────────────────────────────────────────────
target = [f for f in all_forms if f.get("displayName") in TARGET_FORMS]
print(f"\nFormularios que coinciden con el filtro: {len(target)}")

if not target:
    print("Ningún formulario coincide. Verifica los nombres exactos arriba.")
    raise SystemExit(0)

# ── 3. Probar ambos endpoints de submissions por cada formulario ───────────────
for form in target:
    form_id   = form["id"]
    form_name = form["displayName"]

    print(f"\n{'#'*60}")
    print(f"  Formulario: '{form_name}'  (id={form_id})")
    print(f"{'#'*60}")

    # Endpoint A: GET /forms/{form_id}/submissions
    dump(
        f"Endpoint A — GET /forms/{form_id}/submissions",
        get(f"/forms/{form_id}/submissions", {"limit": 5}),
    )

    # Endpoint B: GET /sites/{site_id}/form-submissions?formId={form_id}
    dump(
        f"Endpoint B — GET /sites/{SITE_ID}/form-submissions?formId={form_id}",
        get(f"/sites/{SITE_ID}/form-submissions", {"formId": form_id, "limit": 5}),
    )

    # Endpoint C: GET /sites/{site_id}/form_submissions?formId={form_id}  (underscore)
    dump(
        f"Endpoint C — GET /sites/{SITE_ID}/form_submissions?formId={form_id}",
        get(f"/sites/{SITE_ID}/form_submissions", {"formId": form_id, "limit": 5}),
    )

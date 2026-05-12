#!/usr/bin/env python3
"""
Diagnóstico de conversiones offline subidas a Google Ads.
Consulta offline_conversion_upload_conversion_action_summary
para ver el estado de cada acción de conversión.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

load_dotenv()

CUSTOMER_ID = os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")
STATE_FILE  = "state.json"

CONVERSION_ACTIONS = [
    os.getenv("CONVERSION_QUALIFIED_LEAD", "Qualified Lead"),
    os.getenv("CONVERSION_SQL", "SQL"),
    os.getenv("CONVERSION_CLIENT_WON", "Client Won"),
]

STATUS_LABEL = {
    "GOOD":     "✓ Bueno",
    "WARNING":  "⚠ Advertencia",
    "CRITICAL": "✗ Crítico",
    "UNKNOWN":  "? Desconocido",
    "NO_RECENT_UPLOADS": "— Sin uploads recientes",
}


def build_client() -> GoogleAdsClient:
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id":       os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret":   os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token":   os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "use_proto_plus":  True,
    })


def query_upload_summary(client: GoogleAdsClient) -> list[dict]:
    service = client.get_service("GoogleAdsService")
    query = """
        SELECT
            offline_conversion_upload_conversion_action_summary.conversion_action_name,
            offline_conversion_upload_conversion_action_summary.total_event_count,
            offline_conversion_upload_conversion_action_summary.successful_event_count,
            offline_conversion_upload_conversion_action_summary.pending_event_count,
            offline_conversion_upload_conversion_action_summary.alerts,
            offline_conversion_upload_conversion_action_summary.status,
            offline_conversion_upload_conversion_action_summary.last_upload_date_time
        FROM offline_conversion_upload_conversion_action_summary
    """
    try:
        response = service.search(customer_id=CUSTOMER_ID, query=query)
        rows = []
        for row in response:
            s = row.offline_conversion_upload_conversion_action_summary
            total     = s.total_event_count
            successful = s.successful_event_count
            pending    = s.pending_event_count
            failed     = max(total - successful - pending, 0)
            rows.append({
                "name":        s.conversion_action_name,
                "total":       total,
                "successful":  successful,
                "failed":      failed,
                "pending":     pending,
                "alerts":      list(s.alerts) if s.alerts else [],
                "status":      s.status.name if hasattr(s.status, "name") else str(s.status),
                "last_upload": s.last_upload_date_time,
            })
        return rows
    except GoogleAdsException as ex:
        print(f"\nError al consultar Google Ads API:")
        for error in ex.failure.errors:
            print(f"  {error.message}")
        raise


def load_state() -> dict:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def summarize_state(state: dict) -> dict[str, int]:
    """Cuenta conversiones por acción en el state.json local."""
    counts: dict[str, int] = {}
    for entry in state.values():
        action = entry.get("action", "desconocido")
        counts[action] = counts.get(action, 0) + 1
    return counts


def main():
    print(f"\n{'='*60}")
    print("  DIAGNÓSTICO DE CONVERSIONES OFFLINE — GOOGLE ADS")
    print(f"  Cuenta: {CUSTOMER_ID}")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*60}")

    # ── Estado local ───────────────────────────────────────────────────────────
    state = load_state()
    local_counts = summarize_state(state)

    print(f"\n📁 Estado local ({STATE_FILE}) — conversiones registradas por este script:")
    if local_counts:
        for action in CONVERSION_ACTIONS:
            n = local_counts.get(action, 0)
            print(f"   {action:<30} {n:>5} conversión(es)")
        others = {k: v for k, v in local_counts.items() if k not in CONVERSION_ACTIONS}
        for action, n in others.items():
            print(f"   {action:<30} {n:>5} conversión(es)")
    else:
        print("   (vacío — no se ha subido ninguna conversión aún)")

    # ── Resumen de Google Ads ──────────────────────────────────────────────────
    print(f"\n☁️  Resumen en Google Ads (offline_conversion_upload_conversion_action_summary):")

    client = build_client()
    rows = query_upload_summary(client)

    # Filtrar solo las acciones que nos interesan, luego mostrar el resto
    relevant = [r for r in rows if r["name"] in CONVERSION_ACTIONS]
    others   = [r for r in rows if r["name"] not in CONVERSION_ACTIONS]

    if not relevant:
        print("\n   No se encontraron datos para las acciones configuradas.")
        print("   (Puede tardar hasta 24 h en aparecer tras el primer upload.)")
    else:
        for r in relevant:
            status_str = STATUS_LABEL.get(r["status"], r["status"])
            last = r["last_upload"] or "—"
            print(f"\n   ┌─ {r['name']}")
            print(f"   │  Estado general : {status_str}")
            print(f"   │  Último upload  : {last}")
            print(f"   │  Total enviadas : {r['total']}")
            print(f"   │  Exitosas       : {r['successful']}")
            print(f"   │  Pendientes     : {r['pending']}")
            print(f"   │  Fallidas       : {r['failed']}")
            if r["alerts"]:
                for alert in r["alerts"]:
                    print(f"   │  ⚠ Alerta       : {alert}")
            print(f"   └{'─'*40}")

    if others:
        print(f"\n   Otras acciones en la cuenta ({len(others)}):")
        for r in others:
            print(f"   · {r['name']}: {r['successful']} ok / {r['failed']} fallidas / {r['pending']} pendientes")

    # ── Discrepancias ──────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  Comparación local vs Google Ads:")
    for r in relevant:
        local = local_counts.get(r["name"], 0)
        remote_total = r["total"]
        diff = local - remote_total
        if diff == 0:
            mark = "✓"
        elif diff > 0:
            mark = "⏳"  # subidas localmente pero aún no reflejadas
        else:
            mark = "⚠"
        print(f"   {mark} {r['name']}: {local} local / {remote_total} en Google Ads", end="")
        if diff > 0:
            print(f" ({diff} pendientes de procesar)", end="")
        print()

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

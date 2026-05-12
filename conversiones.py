#!/usr/bin/env python3
"""
Conversiones Offline a Google Ads
Flujo: Webflow (submissions con GCLID) → Pipedrive (calificación) → Google Ads
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("conversiones.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

CONVERSION_QUALIFIED_LEAD = os.getenv("CONVERSION_QUALIFIED_LEAD", "Qualified Lead")
CONVERSION_SQL            = os.getenv("CONVERSION_SQL", "SQL")
CONVERSION_CLIENT_WON     = os.getenv("CONVERSION_CLIENT_WON", "Client Won")


# ─── Webflow ───────────────────────────────────────────────────────────────────

class WebflowClient:
    BASE_URL = "https://api.webflow.com/v2"

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> dict:
        r = self.session.get(f"{self.BASE_URL}{path}", params=params or {})
        r.raise_for_status()
        return r.json()

    def get_all_submissions(self, site_id: str) -> list:
        submissions, offset, limit = [], 0, 100
        while True:
            data = self._get(f"/sites/{site_id}/form_submissions", {"limit": limit, "offset": offset})
            batch = data.get("formSubmissions", [])
            submissions.extend(batch)
            total = data.get("pagination", {}).get("total", 0)
            offset += limit
            if offset >= total:
                break
        return submissions


# ─── Pipedrive ─────────────────────────────────────────────────────────────────

class PipedriveClient:
    BASE_URL = "https://api.pipedrive.com/v1"

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self._deal_fields_cache: dict = {}

    def _get(self, path: str, params: dict = None) -> dict:
        params = {**(params or {}), "api_token": self.token}
        r = self.session.get(f"{self.BASE_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def _deal_field_key(self, label: str) -> Optional[str]:
        if not self._deal_fields_cache:
            fields = self._get("/dealFields").get("data", [])
            self._deal_fields_cache = {f["name"]: f["key"] for f in fields}
        key = self._deal_fields_cache.get(label)
        if not key:
            log.warning(
                f"Campo de deal '{label}' no encontrado. "
                f"Disponibles: {list(self._deal_fields_cache.keys())}"
            )
        return key

    def _deal_field_not_empty(self, deal: dict, label: str) -> bool:
        key = self._deal_field_key(label)
        if not key:
            return False
        val = deal.get(key)
        return val is not None and val != ""

    def search_person_by_email(self, email: str) -> Optional[dict]:
        data = self._get("/persons/search", {"term": email, "fields": "email", "exact_match": 1})
        items = data.get("data", {}).get("items", [])
        return items[0].get("item") if items else None

    def get_person_deals(self, person_id: int) -> list:
        return self._get(f"/persons/{person_id}/deals", {"status": "all_not_deleted"}).get("data") or []

    def is_qualified_lead(self, deal: dict) -> bool:
        return self._deal_field_not_empty(deal, "Calificación del Lead")

    def is_sql(self, deal: dict) -> bool:
        return self._deal_field_not_empty(deal, "Calificación SQL")

    def won_time(self, deal: dict) -> Optional[datetime]:
        if deal.get("status") != "won":
            return None
        raw = deal.get("won_time") or deal.get("close_time")
        if raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return None


# ─── Google Ads ────────────────────────────────────────────────────────────────

class GoogleAdsUploader:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id.replace("-", "")
        self.client = GoogleAdsClient.load_from_dict({
            "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
            "client_id":       os.getenv("GOOGLE_ADS_CLIENT_ID"),
            "client_secret":   os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token":   os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
            "use_proto_plus":  True,
        })
        self._action_cache: dict = {}

    def _get_conversion_action_resource(self, action_name: str) -> Optional[str]:
        if action_name in self._action_cache:
            return self._action_cache[action_name]
        ga_service = self.client.get_service("GoogleAdsService")
        query = f"""
            SELECT conversion_action.resource_name, conversion_action.name
            FROM conversion_action
            WHERE conversion_action.name = '{action_name}'
              AND conversion_action.status = 'ENABLED'
        """
        try:
            for row in ga_service.search(customer_id=self.customer_id, query=query):
                resource = row.conversion_action.resource_name
                self._action_cache[action_name] = resource
                return resource
        except GoogleAdsException as ex:
            log.error(f"Error buscando acción de conversión '{action_name}': {ex}")
            return None
        log.error(f"Acción de conversión '{action_name}' no encontrada o no está habilitada.")
        return None

    @staticmethod
    def _format_datetime(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")

    def upload_conversion(
        self,
        gclid: str,
        action_name: str,
        conversion_time: datetime,
        value: float = 0.0,
        currency: str = "USD",
    ) -> bool:
        resource_name = self._get_conversion_action_resource(action_name)
        if not resource_name:
            return False

        upload_service = self.client.get_service("ConversionUploadService")
        conversion = self.client.get_type("ClickConversion")
        conversion.gclid = gclid
        conversion.conversion_action = resource_name
        conversion.conversion_date_time = self._format_datetime(conversion_time)
        conversion.conversion_value = value
        conversion.currency_code = currency

        request = self.client.get_type("UploadClickConversionsRequest")
        request.customer_id = self.customer_id
        request.conversions.append(conversion)
        request.partial_failure = True

        try:
            response = upload_service.upload_click_conversions(request=request)
            if response.partial_failure_error.code:
                log.error(
                    f"Error parcial '{action_name}' gclid={gclid[:12]}…: "
                    f"code={response.partial_failure_error.code} "
                    f"msg={response.partial_failure_error.message}"
                )
                return False
            log.info(f"  ✓ '{action_name}' subida (gclid={gclid[:12]}…)")
            return True
        except GoogleAdsException as ex:
            for error in ex.failure.errors:
                log.error(f"  ✗ GoogleAdsError '{action_name}': {error.message} [{error.error_code}]")
            return False


# ─── Helpers ───────────────────────────────────────────────────────────────────

def parse_time(raw: Optional[str]) -> datetime:
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


# ─── Orquestador ───────────────────────────────────────────────────────────────

def run():
    print("=== INICIO RUN CONVERSIONES ===", flush=True)
    webflow   = WebflowClient(os.getenv("WEBFLOW_API_TOKEN"))
    pipedrive = PipedriveClient(os.getenv("PIPEDRIVE_API_TOKEN"))
    gads      = GoogleAdsUploader(os.getenv("GOOGLE_ADS_CUSTOMER_ID"))
    site_id   = os.getenv("WEBFLOW_SITE_ID")

    log.info(f"Obteniendo form submissions de Webflow (sitio {site_id})…")
    submissions = webflow.get_all_submissions(site_id)
    log.info(f"{len(submissions)} submission(s) recibidas")

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    leads = []
    for s in submissions:
        submitted_at = s.get("dateSubmitted")
        lead_time = parse_time(submitted_at)
        if lead_time < cutoff:
            continue
        gclid = (s.get("formResponse", {}).get("gclid") or "").strip()
        email = (s.get("formResponse", {}).get("email") or "").strip().lower()
        if not gclid or gclid == "sin_especificar" or not email:
            continue
        leads.append({"gclid": gclid, "email": email, "submitted_at": submitted_at})

    log.info(f"{len(leads)} lead(s) con GCLID y email válidos en los últimos 90 días")

    uploaded = 0

    for lead in leads:
        gclid     = lead["gclid"]
        email     = lead["email"]
        lead_time = parse_time(lead["submitted_at"])

        log.info(f"Lead {email} | gclid={gclid[:16]}…")

        person = pipedrive.search_person_by_email(email)
        if not person:
            log.warning(f"  No encontrado en Pipedrive: {email}")
            continue

        deals = pipedrive.get_person_deals(person["id"])
        if not deals:
            log.info(f"  Sin deals en Pipedrive: {email}")
            continue

        for deal in deals:
            if pipedrive.is_qualified_lead(deal):
                uploaded += gads.upload_conversion(gclid, CONVERSION_QUALIFIED_LEAD, lead_time)

            if pipedrive.is_sql(deal):
                uploaded += gads.upload_conversion(gclid, CONVERSION_SQL, lead_time)

            wt = pipedrive.won_time(deal)
            if wt:
                uploaded += gads.upload_conversion(gclid, CONVERSION_CLIENT_WON, wt)

    log.info(f"Proceso completado. Conversiones enviadas en esta ejecución: {uploaded}")
    print(f"=== FIN RUN. Total subidas: {uploaded} ===", flush=True)


if __name__ == "__main__":
    run()

# conversiones-offline-detecta

Batch script that reads Webflow form submissions, cross-references lead qualification in Pipedrive, and uploads offline conversions to Google Ads.

## How it works

```
Webflow (form submissions + GCLID)
           │
           ▼
    Filter: email + GCLID valid, last 90 days
           │
           ▼
    Pipedrive — search person by email
           │
           ├──► Calificación del Lead  →  upload "Qualified Lead"
           ├──► Calificación SQL       →  upload "SQL"
           └──► Deal ganado            →  upload "Client Won"
           │
           ▼
    Google Ads — UploadClickConversions API
           │
           ▼
    state.json — deduplication (90-day window)
```

## Setup

```bash
cp .env.example .env   # fill in your keys
pip install -r requirements.txt
python conversiones.py
```

## Run modes

| Command | Description |
|---------|-------------|
| `python conversiones.py` | Run batch manually |
| Railway cron | Scheduled weekly via Railway cron job |

## Environment variables

| Variable | Description |
|----------|-------------|
| `WEBFLOW_API_TOKEN` | Webflow API access token |
| `WEBFLOW_SITE_ID` | Webflow site ID |
| `PIPEDRIVE_API_TOKEN` | Pipedrive API token |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads developer token |
| `GOOGLE_ADS_CLIENT_ID` | OAuth2 client ID |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth2 client secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | OAuth2 refresh token |
| `GOOGLE_ADS_CUSTOMER_ID` | Google Ads customer ID (format: 123-456-7890) |
| `CONVERSION_QUALIFIED_LEAD` | Conversion action name (default: `Qualified Lead`) |
| `CONVERSION_SQL` | Conversion action name (default: `SQL`) |
| `CONVERSION_CLIENT_WON` | Conversion action name (default: `Client Won`) |

## Conversion types

| Conversion | Trigger |
|------------|---------|
| `Qualified Lead` | Deal has "Calificación del Lead" field filled |
| `SQL` | Deal has "Calificación SQL" field filled |
| `Client Won` | Deal status = won |

## Deduplication

`state.json` tracks every uploaded conversion by a hash of `gclid + action`. Re-running the script skips already-uploaded conversions. This file is local and not committed — Railway resets it on each deploy, with the 90-day submission window acting as the safety net against duplicates.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| Webflow | Webflow API v2 via `requests` |
| Pipedrive | Pipedrive REST API v1 via `requests` |
| Google Ads | `google-ads` Python SDK |
| Config | `python-dotenv` |
| Deploy | Railway (cron job) |

## License

MIT

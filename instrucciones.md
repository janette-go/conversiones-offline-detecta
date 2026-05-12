# Conversiones Offline a Google Ads

## Descripción

Este proyecto automatiza la subida de conversiones offline a Google Ads a partir de leads generados en Webflow y gestionados en Pipedrive.

## Flujo general

1. Un lead llega desde Webflow junto con su GCLID (Google Click ID), que identifica el clic de Google Ads que originó la visita.
2. El lead se gestiona en Pipedrive, donde se evalúa su calidad mediante dos propiedades:
   - **lead calificado**: indica si el lead pasó un filtro de calificación inicial.
   - **calificacion SQL**: indica si el lead fue calificado como Sales Qualified Lead.
3. Según el estado del lead en Pipedrive, se sube la conversión correspondiente a Google Ads usando el GCLID almacenado.

## Tipos de conversión

| Conversión | Descripción |
|---|---|
| `Qualified Lead` | El lead fue marcado como calificado en Pipedrive |
| `SQL` | El lead alcanzó la calificación de Sales Qualified Lead |
| `Client Won` | El lead se convirtió en cliente (deal ganado en Pipedrive) |

## Variables de entorno requeridas

| Variable | Descripción |
|---|---|
| `WEBFLOW_API_TOKEN` | Token de acceso a la API de Webflow |
| `PIPEDRIVE_API_TOKEN` | Token de acceso a la API de Pipedrive |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Developer token de Google Ads |
| `GOOGLE_ADS_CLIENT_ID` | Client ID de OAuth2 para Google Ads |
| `GOOGLE_ADS_CLIENT_SECRET` | Client Secret de OAuth2 para Google Ads |
| `GOOGLE_ADS_REFRESH_TOKEN` | Refresh token de OAuth2 para Google Ads |
| `GOOGLE_ADS_CUSTOMER_ID` | ID de la cuenta de Google Ads |

# Live Export Endpoint Check — 2026-11-24

The running ConsentX server returned HTTP 200 for both `/api/audit?format=json` and `/api/audit?format=csv`. The JSON and CSV each contain 54 rows. The browser links point to these endpoints, but clicking them in the connected Chrome session produced `ERR_BLOCKED_BY_CLIENT`, so browser file download itself remains unverified.

## Quick Run

```bash
./run.sh "Indiranagar, Bangalore" "MG Road, Bangalore"
```

The first run will auto-create a local venv and install dependencies.

## Local Setup

```bash
cd life-ops-agent
./setup.sh
./run.sh --doctor
```

`./setup.sh` now bootstraps both:
- `life-ops-agent/.env`
- `life-ops-agent/frontend/.env`

Before live trip lookups will work, replace the placeholder values in `.env` with real keys:

```bash
WEATHERAPI_KEY=...
ORS_API_KEY=...
```

Optional:

```bash
NEWS_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_MAPS_API_KEY=...
ROUTING_PROVIDER=google
```

For stronger AI results with the current OpenAI model family, a good default setup is:

```bash
OPENAI_API_KEY=...
OPENAI_DECISION_MODEL=gpt-5.2
OPENAI_PARSER_MODEL=gpt-5-mini
```

This follows OpenAI's current guidance that `gpt-5.2` is the best general-purpose model and `gpt-5-mini` is a strong faster/cost-efficient option for well-defined tasks like query parsing.

If `./run.sh --doctor` prints `MISSING`, the value is still empty or still a placeholder such as `your_weatherapi_key`.

For auth-enabled flows, set a real `AUTH_SECRET` before deploying. If you leave it unset, the app falls back to a development secret, which is not safe for production.

## CLI Options

```bash
./run.sh "Indiranagar, Bangalore" "MG Road, Bangalore" --format json
./run.sh "Indiranagar, Bangalore" "MG Road, Bangalore" --provider osrm
./run.sh "Indiranagar, Bangalore" "MG Road, Bangalore" --provider google
./run.sh --query "Should I travel from Indiranagar to MG Road today?"
./run.sh "Indiranagar, Bangalore" "MG Road, Bangalore" --quiet
./run.sh --purge-cache "Indiranagar, Bangalore"
./run.sh --clear-route-cache
```

## Caching (Auto)

The app caches geocoding, routes, and weather responses to reduce API calls.
Defaults:
- Weather cache TTL: 10 minutes
- Route cache TTL: 15 minutes
- Geocode cache TTL: 7 days

You can override in `.env`:
```
WEATHER_CACHE_TTL_SEC=600
ROUTE_CACHE_TTL_SEC=900
GEOCODE_CACHE_TTL_SEC=604800
```

## One-Time Setup (Optional)

```bash
./setup.sh
```

Then add your keys in `.env` (created from `.env.example`):

```
WEATHERAPI_KEY=your_weatherapi_key
ORS_API_KEY=your_ors_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
NEWS_API_KEY=your_newsapi_key
OPENAI_API_KEY=your_openai_api_key
ORS_BASE_URL=https://api.openrouteservice.org
# Staging hosts may require the /ors base path:
# ORS_BASE_URL=https://staging.openrouteservice.org/ors
# Routing provider: ors (default), osrm (no key needed), or google
# ROUTING_PROVIDER=google
# Optional: traffic model for Google Directions (best_guess, optimistic, pessimistic)
# GOOGLE_TRAFFIC_MODEL=best_guess
# Optional: Google Geocoding API host
# GOOGLE_GEOCODE_BASE_URL=https://maps.googleapis.com/maps/api/geocode/json
# Recommended OpenAI setup for this app:
# OPENAI_DECISION_MODEL=gpt-5.2
# OPENAI_PARSER_MODEL=gpt-5-mini
# Optional: News API host
# NEWS_API_BASE_URL=https://newsapi.org/v2/everything
# If ORS_BASE_URL is a staging host without geocoding, set:
# ORS_GEOCODE_BASE_URL=https://api.openrouteservice.org
# Optional Open-Meteo geocoding (key-free)
# OPEN_METEO_GEOCODE_BASE_URL=https://geocoding-api.open-meteo.com/v1/search
# Optional: Nominatim fallback settings
# NOMINATIM_USER_AGENT=life-ops-agent/1.0 (you@example.com)
```

## API
- `GET /context` (source/destination)
- `GET /decision` (natural-language query)

### Smoke Test

Start the backend:

```bash
./run.sh --serve
```

Then query it from another terminal:

```bash
curl "http://127.0.0.1:8000/decision?query=Should%20I%20travel%20from%20Indiranagar%20to%20MG%20Road%20today%3F"
```

## Tests

```bash
cd life-ops-agent
./.venv/bin/python -m pytest -q
```

## Deployment Notes

Frontend:
- If you deploy `frontend` separately on Vercel, set `VITE_API_BASE_URL` to your backend origin, for example `https://your-backend.onrender.com`.
- If `VITE_API_BASE_URL` is unset, the app uses `http://127.0.0.1:8000` only for local development. In non-local environments it falls back to the current site origin.

Backend:
- Set `AUTH_SECRET` to a long random value for production.
- The default database is local SQLite. On Render free web services, local files are ephemeral, so user accounts, preferences, and trip history will be lost on restart or redeploy unless you move persistence to a durable store.
```

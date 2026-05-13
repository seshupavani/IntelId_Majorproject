import json
import os
import time
from pathlib import Path
import requests

from backend.config import has_configured_value

API_KEY = os.getenv("ORS_API_KEY", "YOUR_ORS_API_KEY")
BASE_URL = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org")
GEOCODE_BASE_URL = os.getenv("ORS_GEOCODE_BASE_URL", BASE_URL)
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_MAPS_BASE_URL = os.getenv(
    "GOOGLE_MAPS_BASE_URL", "https://maps.googleapis.com/maps/api/directions/json"
)
GOOGLE_GEOCODE_BASE_URL = os.getenv(
    "GOOGLE_GEOCODE_BASE_URL", "https://maps.googleapis.com/maps/api/geocode/json"
)
OPEN_METEO_GEOCODE_BASE_URL = os.getenv(
    "OPEN_METEO_GEOCODE_BASE_URL", "https://geocoding-api.open-meteo.com/v1/search"
)
GOOGLE_TRAFFIC_MODEL = os.getenv("GOOGLE_TRAFFIC_MODEL")
GEOCODE_CACHE_TTL_SEC = int(os.getenv("GEOCODE_CACHE_TTL_SEC", "604800"))
ROUTE_CACHE_TTL_SEC = int(os.getenv("ROUTE_CACHE_TTL_SEC", "900"))
MAPS_CACHE_PATH = os.getenv("MAPS_CACHE_PATH")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "life-ops-agent/1.0")


def _get_routing_provider():
    return os.getenv("ROUTING_PROVIDER", "ors").lower()


def _get_routing_fallback():
    return os.getenv("ROUTING_FALLBACK", "osrm").lower()

def _format_duration(seconds):
    if seconds is None:
        return None
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    rem = minutes % 60
    if rem == 0:
        return f"{hours} hr"
    return f"{hours} hr {rem} min"

def _format_distance(meters):
    if meters is None:
        return None
    km = meters / 1000.0
    if km < 1:
        return f"{int(round(meters))} m"
    return f"{km:.1f} km"

def _parse_coords(value):
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        return None
    return [lon, lat]


def get_coords(location, timeout=10):
    if not location:
        raise ValueError("location is required")
    
    # Try parsing as coordinates first
    coords = _parse_coords(location)
    if coords:
        return coords
    
    # Fall back to geocoding
    try:
        return _geocode(location, timeout=timeout)
    except Exception as e:
        # Try Nominatim as final fallback
        try:
            return _geocode_nominatim(location, timeout=timeout)
        except Exception as fallback_error:
            raise ValueError(f"Unable to geocode location '{location}': {e}") from e

def _default_cache_path():
    base_dir = Path(__file__).resolve().parents[2]
    return base_dir / ".cache" / "maps.json"

def _load_cache(path):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {"geocode": {}, "route": {}}

def _save_cache(path, cache):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache))
    except Exception as e:
        # Log error but don't fail the operation
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to save cache to {path}: {e}")

def _get_cached(cache, section, key, ttl_sec):
    entry = (cache.get(section) or {}).get(key)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > ttl_sec:
        return None
    return entry.get("value")

def _set_cached(cache, section, key, value):
    cache.setdefault(section, {})[key] = {"ts": time.time(), "value": value}

def purge_geocode_cache(text):
    if not text:
        return False
    cache_path = Path(MAPS_CACHE_PATH) if MAPS_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    key = f"geocode|{GEOCODE_BASE_URL}|{text.strip().lower()}"
    coords = (cache.get("geocode") or {}).pop(key, None)
    removed = False
    if coords is not None:
        removed = True
    # Also remove routes that contain these coords (best-effort).
    if coords and isinstance(coords, dict):
        coords = coords.get("value")
    if coords:
        coord_str = str(coords)
        routes = cache.get("route") or {}
        to_delete = [k for k in routes.keys() if coord_str in k]
        for k in to_delete:
            routes.pop(k, None)
            removed = True
        cache["route"] = routes
    if removed:
        _save_cache(cache_path, cache)
    return removed

def clear_route_cache():
    cache_path = Path(MAPS_CACHE_PATH) if MAPS_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    if cache.get("route"):
        cache["route"] = {}
        _save_cache(cache_path, cache)
        return True
    return False

def _route_osrm(start_coords, end_coords, timeout=10):
    cache_path = Path(MAPS_CACHE_PATH) if MAPS_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    cache_key = f"osrm|{OSRM_BASE_URL}|{start_coords}|{end_coords}"
    cached = _get_cached(cache, "route", cache_key, ROUTE_CACHE_TTL_SEC)
    if cached:
        return cached

    base = OSRM_BASE_URL.rstrip("/")
    coords = f"{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}"
    url = f"{base}/route/v1/driving/{coords}"
    params = {"overview": "false"}
    res = requests.get(url, params=params, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"OSRM error ({res.status_code}): {data}")

    routes = data.get("routes") or []
    if not routes:
        raise ValueError("OSRM error: no routes found")

    duration = routes[0].get("duration")
    distance = routes[0].get("distance")
    result = {
        "duration": _format_duration(duration),
        "distance": _format_distance(distance),
        "source": "osrm",
    }
    _set_cached(cache, "route", cache_key, result)
    _save_cache(cache_path, cache)
    return result

def _route_google(start_coords, end_coords, timeout=10):
    if not has_configured_value(GOOGLE_MAPS_API_KEY):
        raise ValueError("GOOGLE_MAPS_API_KEY is not set")

    cache_path = Path(MAPS_CACHE_PATH) if MAPS_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    cache_key = (
        f"google|{GOOGLE_MAPS_BASE_URL}|{start_coords}|{end_coords}|{GOOGLE_TRAFFIC_MODEL}"
    )
    cached = _get_cached(cache, "route", cache_key, ROUTE_CACHE_TTL_SEC)
    if cached:
        return cached

    base = GOOGLE_MAPS_BASE_URL.rstrip("/")
    start = f"{start_coords[1]},{start_coords[0]}"
    end = f"{end_coords[1]},{end_coords[0]}"
    params = {
        "origin": start,
        "destination": end,
        "key": GOOGLE_MAPS_API_KEY,
        "departure_time": "now",
    }
    if GOOGLE_TRAFFIC_MODEL:
        params["traffic_model"] = GOOGLE_TRAFFIC_MODEL

    res = requests.get(base, params=params, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"Google Directions API error ({res.status_code}): {data}")

    routes = data.get("routes") or []
    if not routes:
        raise ValueError("Google Directions API error: no routes found")

    legs = routes[0].get("legs") or []
    if not legs:
        raise ValueError("Google Directions API error: missing legs")

    leg = legs[0]
    duration = (leg.get("duration_in_traffic") or {}).get("value")
    if duration is None:
        duration = (leg.get("duration") or {}).get("value")
    distance = (leg.get("distance") or {}).get("value")

    result = {
        "duration": _format_duration(duration),
        "distance": _format_distance(distance),
        "source": "google_directions",
    }
    _set_cached(cache, "route", cache_key, result)
    _save_cache(cache_path, cache)
    return result

def _geocode_nominatim(text, timeout=10):
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    params = {"q": text, "format": "json", "limit": 1}
    res = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"Nominatim error ({res.status_code}): {data}")

    if not data:
        raise ValueError(f"Nominatim error: no results for '{text}'")

    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])
    return [lon, lat]

def _geocode_google(text, timeout=10):
    if not has_configured_value(GOOGLE_MAPS_API_KEY):
        raise ValueError("GOOGLE_MAPS_API_KEY is not set")
    params = {"address": text, "key": GOOGLE_MAPS_API_KEY}
    res = requests.get(GOOGLE_GEOCODE_BASE_URL, params=params, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"Google Geocoding API error ({res.status_code}): {data}")

    status = data.get("status")
    if status != "OK":
        raise ValueError(f"Google Geocoding API error: {status}")

    results = data.get("results") or []
    if not results:
        raise ValueError("Google Geocoding API error: no results")

    location = (results[0].get("geometry") or {}).get("location") or {}
    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        raise ValueError("Google Geocoding API error: missing location")
    return [lng, lat]

def _geocode_open_meteo(text, timeout=10):
    params = {"name": text, "count": 1, "language": "en", "format": "json"}
    res = requests.get(OPEN_METEO_GEOCODE_BASE_URL, params=params, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"Open-Meteo geocoding error ({res.status_code}): {data}")

    results = data.get("results") or []
    if not results:
        raise ValueError("Open-Meteo geocoding error: no results")

    lat = results[0].get("latitude")
    lon = results[0].get("longitude")
    if lat is None or lon is None:
        raise ValueError("Open-Meteo geocoding error: missing coordinates")
    return [lon, lat]

def _geocode(text, timeout=10):
    cache_path = Path(MAPS_CACHE_PATH) if MAPS_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    cache_key = f"geocode|{GEOCODE_BASE_URL}|{text.strip().lower()}"
    cached = _get_cached(cache, "geocode", cache_key, GEOCODE_CACHE_TTL_SEC)
    if cached:
        return cached

    if not has_configured_value(API_KEY) or not GEOCODE_BASE_URL:
        if has_configured_value(GOOGLE_MAPS_API_KEY):
            try:
                coords = _geocode_google(text, timeout=timeout)
            except Exception:
                try:
                    coords = _geocode_open_meteo(text, timeout=timeout)
                except Exception:
                    coords = _geocode_nominatim(text, timeout=timeout)
        else:
            try:
                coords = _geocode_open_meteo(text, timeout=timeout)
            except Exception:
                coords = _geocode_nominatim(text, timeout=timeout)
        _set_cached(cache, "geocode", cache_key, coords)
        _save_cache(cache_path, cache)
        return coords

    url = f"{GEOCODE_BASE_URL}/geocode/search"
    params = {"api_key": API_KEY, "text": text, "size": 1}
    res = requests.get(url, params=params, timeout=timeout)

    if res.status_code != 200:
        if has_configured_value(GOOGLE_MAPS_API_KEY):
            try:
                coords = _geocode_google(text, timeout=timeout)
            except Exception:
                try:
                    coords = _geocode_open_meteo(text, timeout=timeout)
                except Exception:
                    coords = _geocode_nominatim(text, timeout=timeout)
        else:
            try:
                coords = _geocode_open_meteo(text, timeout=timeout)
            except Exception:
                coords = _geocode_nominatim(text, timeout=timeout)
        _set_cached(cache, "geocode", cache_key, coords)
        _save_cache(cache_path, cache)
        return coords

    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    features = data.get("features") or []
    if not features:
        if has_configured_value(GOOGLE_MAPS_API_KEY):
            try:
                coords = _geocode_google(text, timeout=timeout)
            except Exception:
                try:
                    coords = _geocode_open_meteo(text, timeout=timeout)
                except Exception:
                    coords = _geocode_nominatim(text, timeout=timeout)
        else:
            try:
                coords = _geocode_open_meteo(text, timeout=timeout)
            except Exception:
                coords = _geocode_nominatim(text, timeout=timeout)
        _set_cached(cache, "geocode", cache_key, coords)
        _save_cache(cache_path, cache)
        return coords

    coords = (features[0].get("geometry") or {}).get("coordinates")
    if not coords or len(coords) != 2:
        if has_configured_value(GOOGLE_MAPS_API_KEY):
            try:
                coords = _geocode_google(text, timeout=timeout)
            except Exception:
                try:
                    coords = _geocode_open_meteo(text, timeout=timeout)
                except Exception:
                    coords = _geocode_nominatim(text, timeout=timeout)
        else:
            try:
                coords = _geocode_open_meteo(text, timeout=timeout)
            except Exception:
                coords = _geocode_nominatim(text, timeout=timeout)
        _set_cached(cache, "geocode", cache_key, coords)
        _save_cache(cache_path, cache)
        return coords
    _set_cached(cache, "geocode", cache_key, coords)
    _save_cache(cache_path, cache)
    return coords

def _request_directions(url, params, timeout):
    res = requests.get(url, params=params, timeout=timeout)
    if res.status_code == 404:
        return res, None
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"Directions API error ({res.status_code}): {data}")
    return res, data


def _extract_ors_summary(data):
    routes = data.get("routes") or []
    if routes:
        summary = routes[0].get("summary") or {}
        return summary.get("duration"), summary.get("distance")

    features = data.get("features") or []
    if features:
        properties = features[0].get("properties") or {}
        summary = properties.get("summary") or {}
        if summary:
            return summary.get("duration"), summary.get("distance")

        segments = properties.get("segments") or []
        if segments:
            segment_summary = segments[0] or {}
            return segment_summary.get("duration"), segment_summary.get("distance")

    return None, None

def get_eta(source, destination, timeout=10):
    if not source or not destination:
        raise ValueError("source and destination are required")

    try:
        start_coords = get_coords(source, timeout=timeout)
        end_coords = get_coords(destination, timeout=timeout)
    except Exception as e:
        raise ValueError(f"Failed to get coordinates: {e}") from e

    routing_provider = _get_routing_provider()

    if routing_provider == "google":
        try:
            return _route_google(start_coords, end_coords, timeout=timeout)
        except Exception as e:
            raise ValueError(f"Google routing failed: {e}") from e

    if routing_provider == "osrm":
        try:
            return _route_osrm(start_coords, end_coords, timeout=timeout)
        except Exception as e:
            raise ValueError(f"OSRM routing failed: {e}") from e

    # ORS routing
    if not has_configured_value(API_KEY):
        raise ValueError("ORS_API_KEY is not set")

    cache_path = Path(MAPS_CACHE_PATH) if MAPS_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    cache_key = f"ors|{BASE_URL}|{start_coords}|{end_coords}"
    cached = _get_cached(cache, "route", cache_key, ROUTE_CACHE_TTL_SEC)
    if cached:
        return cached

    url = f"{BASE_URL}/v2/directions/driving-car"
    params = {
        "api_key": API_KEY,
        "start": f"{start_coords[0]},{start_coords[1]}",
        "end": f"{end_coords[0]},{end_coords[1]}",
    }
    
    try:
        res, data = _request_directions(url, params, timeout)
    except Exception as e:
        raise ValueError(f"ORS routing failed: {e}") from e
    
    if res.status_code == 404:
        base = BASE_URL.rstrip("/")
        if not base.endswith("/ors"):
            alt_base = f"{base}/ors"
            alt_url = f"{alt_base}/v2/directions/driving-car"
            try:
                res, data = _request_directions(alt_url, params, timeout)
            except Exception as e:
                raise ValueError(f"ORS routing failed: {e}") from e
        
        if res.status_code == 404:
            if _get_routing_fallback() == "osrm":
                try:
                    return _route_osrm(start_coords, end_coords, timeout=timeout)
                except Exception as fallback_error:
                    raise ValueError(
                        "Directions API error: endpoint not found. "
                        "Try setting ORS_BASE_URL to https://api.openrouteservice.org "
                        "or https://staging.openrouteservice.org/ors"
                    ) from fallback_error
            else:
                raise ValueError(
                    "Directions API error: endpoint not found. "
                    "Try setting ORS_BASE_URL to https://api.openrouteservice.org "
                    "or https://staging.openrouteservice.org/ors"
                )

    duration, distance = _extract_ors_summary(data)
    if duration is None or distance is None:
        if _get_routing_fallback() == "osrm":
            try:
                return _route_osrm(start_coords, end_coords, timeout=timeout)
            except Exception as fallback_error:
                raise ValueError("Directions API error: no routes found") from fallback_error
        raise ValueError("Directions API error: no routes found")

    result = {
        "duration": _format_duration(duration),
        "distance": _format_distance(distance),
        "source": "openrouteservice",
    }
    _set_cached(cache, "route", cache_key, result)
    _save_cache(cache_path, cache)
    return result

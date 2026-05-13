import json
import os
import time
from pathlib import Path

import requests

from backend.services.maps import get_coords

AQI_BASE_URL = os.getenv(
    "AQI_BASE_URL", "https://air-quality-api.open-meteo.com/v1/air-quality"
)
AQI_CACHE_TTL_SEC = int(os.getenv("AQI_CACHE_TTL_SEC", "1800"))
AQI_CACHE_PATH = os.getenv("AQI_CACHE_PATH")


def _default_cache_path():
    base_dir = Path(__file__).resolve().parents[2]
    return base_dir / ".cache" / "aqi.json"


def _load_cache(path):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {"aqi": {}}


def _save_cache(path, cache):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache))
    except Exception as e:
        # Log error but don't fail the operation
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to save cache to {path}: {e}")


def _get_cached(cache, key):
    entry = (cache.get("aqi") or {}).get(key)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > AQI_CACHE_TTL_SEC:
        return None
    return entry.get("value")


def _set_cached(cache, key, value):
    cache.setdefault("aqi", {})[key] = {"ts": time.time(), "value": value}


def _categorize_us_aqi(value):
    if value is None:
        return None
    if value <= 50:
        return "good"
    if value <= 100:
        return "moderate"
    if value <= 150:
        return "unhealthy_sensitive"
    if value <= 200:
        return "unhealthy"
    if value <= 300:
        return "very_unhealthy"
    return "hazardous"


def _latest_value(values):
    if not values:
        return None
    for item in reversed(values):
        if item is not None:
            return item
    return None


def get_aqi(destination, timeout=10):
    if not destination:
        raise ValueError("destination is required for AQI lookup")

    try:
        coords = get_coords(destination, timeout=timeout)
    except Exception as e:
        raise ValueError(f"Failed to get coordinates for '{destination}': {e}") from e
    
    cache_key = f"aqi|{coords}"

    cache_path = Path(AQI_CACHE_PATH) if AQI_CACHE_PATH else _default_cache_path()
    cache = _load_cache(cache_path)
    cached = _get_cached(cache, cache_key)
    if cached:
        return cached

    base = AQI_BASE_URL.rstrip("/")
    params = {
        "latitude": coords[1],
        "longitude": coords[0],
        "hourly": "us_aqi",
        "timezone": "auto",
    }
    
    try:
        res = requests.get(base, params=params, timeout=timeout)
        data = res.json()
    except requests.exceptions.Timeout:
        raise ValueError(f"AQI API timeout after {timeout}s")
    except Exception as e:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"AQI API error ({res.status_code}): {data}")

    aqi_value = None
    current = data.get("current") or {}
    if "us_aqi" in current:
        aqi_value = current.get("us_aqi")

    if aqi_value is None:
        hourly = data.get("hourly") or {}
        aqi_value = _latest_value(hourly.get("us_aqi"))

    result = {
        "aqi": aqi_value,
        "category": _categorize_us_aqi(aqi_value),
        "source": "open-meteo",
    }
    _set_cached(cache, cache_key, result)
    _save_cache(cache_path, cache)
    return result

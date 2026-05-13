import json
import os
import time
from pathlib import Path

import requests

from backend.config import has_configured_value

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_CONFIGURED = has_configured_value(NEWS_API_KEY)
NEWS_API_BASE_URL = os.getenv(
    "NEWS_API_BASE_URL", "https://newsapi.org/v2/everything"
)
NEWS_CACHE_TTL_SEC = int(os.getenv("NEWS_CACHE_TTL_SEC", "900"))
NEWS_CACHE_PATH = os.getenv("NEWS_CACHE_PATH")


def _default_cache_path():
    base_dir = Path(__file__).resolve().parents[2]
    return base_dir / ".cache" / "news.json"


def _load_cache(path):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {"news": {}}


def _save_cache(path, cache):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache))
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to save cache to {path}: {e}")


def _get_cached(cache, key):
    entry = (cache.get("news") or {}).get(key)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > NEWS_CACHE_TTL_SEC:
        return None
    return entry.get("value")


def _set_cached(cache, key, value):
    cache.setdefault("news", {})[key] = {"ts": time.time(), "value": value}


def _normalize_articles(articles):
    normalized = []
    for item in articles or []:
        source = (item.get("source") or {}).get("name")
        normalized.append(
            {
                "title": item.get("title"),
                "description": item.get("description"),
                "source": source,
                "url": item.get("url"),
                "published_at": item.get("publishedAt"),
            }
        )
    return normalized


def get_news(query, timeout=10, max_articles=5):
    if not NEWS_API_CONFIGURED:
        raise ValueError("NEWS_API_KEY is not set")
    if not query:
        raise ValueError("query is required for news lookup")

    cache_path = Path(NEWS_CACHE_PATH) if NEWS_CACHE_PATH else _default_cache_path()
    cache_key = query.strip().lower()
    cache = _load_cache(cache_path)
    cached = _get_cached(cache, cache_key)
    if cached:
        return cached

    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "apiKey": NEWS_API_KEY,
    }

    res = requests.get(NEWS_API_BASE_URL, params=params, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200 or data.get("status") != "ok":
        raise ValueError(f"News API error ({res.status_code}): {data}")

    articles = _normalize_articles(data.get("articles") or [])
    result = {
        "query": query,
        "articles": articles,
        "source": "newsapi",
    }
    _set_cached(cache, cache_key, result)
    _save_cache(cache_path, cache)
    return result

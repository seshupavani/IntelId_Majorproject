import json
import os
import re
from datetime import datetime, timedelta

import requests

from backend.config import has_configured_value

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_PARSER_MODEL = os.getenv(
    "OPENAI_PARSER_MODEL",
    os.getenv("OPENAI_DECISION_MODEL", "gpt-5-mini"),
)
OPENAI_TIMEOUT_SEC = int(os.getenv("OPENAI_TIMEOUT_SEC", "15"))


def _simple_time_hint(text):
    if not text:
        return None
    lowered = text.lower()
    now = datetime.now()
    if "today" in lowered:
        return now.strftime("%Y-%m-%d")
    if "tomorrow" in lowered:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if "tonight" in lowered:
        return now.strftime("%Y-%m-%d")
    return None


def _clean_location(value):
    if not value:
        return value
    cleaned = value.strip().rstrip("?.! ,")
    cleaned = re.sub(
        r"^(check if i can|can i|should i|i want to|i need to|please)\s+",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"^(travel|go|visit|head|commute)\s+to\s+",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"\b(today|tomorrow|tonight|now|this\s+evening|this\s+morning)\b.*$",
        "",
        cleaned,
        flags=re.I,
    ).strip().rstrip("?.! ,")
    return cleaned or value.strip()


def _heuristic_parse(query):
    source = None
    destination = None
    topic = None

    match = re.search(r"\bfrom\s+(?P<source>.+?)\s+to\s+(?P<dest>.+)", query, re.I)
    if match:
        source = _clean_location(match.group("source"))
        destination = _clean_location(match.group("dest"))
    else:
        match = re.search(
            r"\b(visit|travel|go|head|commute)\s+to\s+(?P<dest>.+?)\s+from\s+(?P<source>.+)",
            query,
            re.I,
        )
        if match:
            destination = _clean_location(match.group("dest"))
            source = _clean_location(match.group("source"))
        else:
            match = re.search(
                r"\bvisit\s+(?P<dest>.+?)\s+from\s+(?P<source>.+)",
                query,
                re.I,
            )
            if match:
                destination = _clean_location(match.group("dest"))
                source = _clean_location(match.group("source"))
            else:
                match = re.search(
                    r"\bto\s+(?P<dest>.+?)\s+from\s+(?P<source>.+)",
                    query,
                    re.I,
                )
                if match:
                    destination = _clean_location(match.group("dest"))
                    source = _clean_location(match.group("source"))
                else:
                    match = re.search(r"\btravel\s+to\s+(?P<dest>.+)", query, re.I)
                    if match:
                        destination = _clean_location(match.group("dest"))
                    else:
                        match = re.search(r"\bgo\s+to\s+(?P<dest>.+)", query, re.I)
                        if match:
                            destination = _clean_location(match.group("dest"))
                        else:
                            match = re.search(r"\bvisit\s+(?P<dest>.+)", query, re.I)
                            if match:
                                destination = _clean_location(match.group("dest"))
                            else:
                                match = re.search(r"\bto\s+(?P<dest>[^,.;]+)", query, re.I)
                                if match:
                                    destination = _clean_location(match.group("dest"))

    lowered = query.lower()
    if any(word in lowered for word in ["event", "concert", "meeting", "wedding", "festival"]):
        decision_type = "event"
    elif any(word in lowered for word in ["travel", "commute", "go", "drive", "ride", "walk", "bike", "flight"]):
        decision_type = "travel"
    else:
        decision_type = "daily"

    if decision_type != "travel":
        topic = destination or query.strip()

    needs = {
        "weather": bool(decision_type in {"travel", "event"} or "weather" in lowered),
        "eta": bool(decision_type == "travel" and source and destination),
        "aqi": bool(decision_type in {"travel", "event"}),
        "news": bool(
            decision_type in {"event", "daily"}
            or "news" in lowered
            or "risk" in lowered
        ),
    }

    return {
        "decision_type": decision_type,
        "source": source,
        "destination": destination,
        "topic": topic,
        "datetime": _simple_time_hint(query),
        "needs": needs,
    }


def _post_process(parsed, query):
    if not parsed:
        return parsed
    if parsed.get("destination") and not parsed.get("source"):
        match = re.search(
            r"(?P<dest>.+?)\s+from\s+(?P<source>.+)",
            parsed.get("destination"),
            re.I,
        )
        if match:
            parsed["destination"] = match.group("dest")
            parsed["source"] = match.group("source")
    if parsed.get("source"):
        parsed["source"] = _clean_location(parsed.get("source"))
    if parsed.get("destination"):
        parsed["destination"] = _clean_location(parsed.get("destination"))
    if not parsed.get("destination") and query:
        fallback = _heuristic_parse(query)
        if fallback.get("destination"):
            parsed["destination"] = fallback.get("destination")
    if parsed.get("topic"):
        parsed["topic"] = _clean_location(parsed.get("topic"))
    return parsed


def _call_openai_parser(query, timeout):
    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a query parser for a decision-support assistant. "
        "Extract structured fields from the user's natural-language query. "
        "Be conservative: set fields to null when unknown."
    )
    user_prompt = f"Query: {query}"

    payload = {
        "model": OPENAI_PARSER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "parsed_query",
                "schema": {
                    "type": "object",
                    "properties": {
                        "decision_type": {
                            "type": "string",
                            "enum": ["travel", "event", "daily"],
                        },
                        "source": {"type": ["string", "null"]},
                        "destination": {"type": ["string", "null"]},
                        "topic": {"type": ["string", "null"]},
                        "datetime": {"type": ["string", "null"]},
                        "needs": {
                            "type": "object",
                            "properties": {
                                "weather": {"type": "boolean"},
                                "eta": {"type": "boolean"},
                                "aqi": {"type": "boolean"},
                                "news": {"type": "boolean"},
                            },
                            "required": ["weather", "eta", "aqi", "news"],
                            "additionalProperties": False,
                        },
                    },
                    "required": [
                        "decision_type",
                        "source",
                        "destination",
                        "topic",
                        "datetime",
                        "needs",
                    ],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        "temperature": 0,
    }

    res = requests.post(url, headers=headers, json=payload, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"OpenAI parser error ({res.status_code}): {data}")

    content = (
        (data.get("choices") or [{}])[0]
        .get("message", {})
        .get("content")
    )
    if not content:
        raise ValueError("OpenAI parser error: empty response")

    parsed = json.loads(content)
    return parsed


def parse_query(query, timeout=None):
    if not query:
        raise ValueError("query is required")

    if not has_configured_value(OPENAI_API_KEY):
        return _post_process(_heuristic_parse(query), query)

    try:
        parsed = _call_openai_parser(query, timeout or OPENAI_TIMEOUT_SEC)
    except Exception:
        parsed = _heuristic_parse(query)

    parsed = _post_process(parsed, query)
    heuristic = _heuristic_parse(query)
    if heuristic.get("source") and not parsed.get("source"):
        parsed["source"] = heuristic.get("source")
    if heuristic.get("destination") and not parsed.get("destination"):
        parsed["destination"] = heuristic.get("destination")
    if heuristic.get("source") and heuristic.get("destination"):
        parsed["source"] = heuristic.get("source")
        parsed["destination"] = heuristic.get("destination")
    if not parsed.get("datetime"):
        parsed["datetime"] = _simple_time_hint(query)
    if not parsed.get("needs"):
        parsed["needs"] = _heuristic_parse(query).get("needs")

    return parsed

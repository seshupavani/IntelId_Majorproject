import json
import os

import requests

from backend.config import has_configured_value


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_DECISION_MODEL = os.getenv("OPENAI_DECISION_MODEL", "gpt-5.2")
OPENAI_TIMEOUT_SEC = int(os.getenv("OPENAI_TIMEOUT_SEC", "15"))


def generate_decision(
    weather,
    distance,
    duration,
    aqi=None,
    news=None,
    query=None,
    risk=None,
    timeout=None,
):
    if not has_configured_value(OPENAI_API_KEY):
        raise ValueError("OPENAI_API_KEY is not set")
    
    # Validate inputs
    if not weather and not distance and not duration and not query:
        raise ValueError("At least one of weather, distance, duration, or query must be provided")

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a decision assistant. "
        "Given the user query and real-time context, recommend the best action. "
        "For local trips, options like walking, biking, or a cab can make sense. "
        "For intercity trips or travel that is roughly 80 km+ or 120 minutes+, do not recommend walking, biking, or a local cab. "
        "Prefer bus, train, or flight for those longer trips. "
        "Return ONLY JSON with action, reason, confidence (0 to 1)."
    )

    news_summary = None
    if isinstance(news, dict):
        articles = news.get("articles") or []
        titles = [a.get("title") for a in articles if a.get("title")]
        if titles:
            news_summary = "; ".join(titles[:3])

    risk_summary = None
    if isinstance(risk, dict) and risk.get("relevant"):
        factors = risk.get("factors") or []
        if factors:
            risk_summary = "; ".join(factors[:3])

    user_prompt = (
        f"Query: {query}\n"
        f"Weather: {weather}\n"
        f"Distance: {distance}\n"
        f"Duration: {duration}\n"
        f"AQI: {aqi}\n"
        f"News: {news_summary}\n"
        f"Risk factors: {risk_summary}\n"
    )

    payload = {
        "model": OPENAI_DECISION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "decision_output",
                "schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["action", "reason", "confidence"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        "temperature": 0.2,
    }

    try:
        res = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout or OPENAI_TIMEOUT_SEC,
        )
        data = res.json()
    except requests.exceptions.Timeout:
        raise ValueError(f"OpenAI API timeout after {timeout or OPENAI_TIMEOUT_SEC}s")
    except Exception as e:
        res.raise_for_status()
        raise

    if res.status_code != 200:
        raise ValueError(f"OpenAI API error ({res.status_code}): {data}")

    content = (
        (data.get("choices") or [{}])[0]
        .get("message", {})
        .get("content")
    )
    if not content:
        raise ValueError("OpenAI API error: empty response content")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI API error: invalid JSON response: {content}") from e
    
    action = parsed.get("action")
    reason = parsed.get("reason")
    confidence = parsed.get("confidence")
    
    if not action or not reason or confidence is None:
        raise ValueError("OpenAI API error: invalid decision format")

    return {
        "action": action,
        "reason": reason,
        "confidence": float(confidence),
        "model": OPENAI_DECISION_MODEL,
    }

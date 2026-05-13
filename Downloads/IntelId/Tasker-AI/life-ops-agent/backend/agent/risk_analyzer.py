def _contains_any(text, terms):
    if not text:
        return False
    lowered = text.lower()
    return any(term in lowered for term in terms)


def analyze_risk(context, parsed_query=None):
    factors = []
    score = 0.0

    weather = (context.get("weather") or {}).get("condition")
    temperature = (context.get("weather") or {}).get("temperature")
    if _contains_any(weather, ["storm", "thunder", "rain", "drizzle", "snow", "hail"]):
        factors.append("Inclement weather expected")
        score += 0.3
    if temperature is not None and (temperature >= 35 or temperature <= 5):
        factors.append("Extreme temperature")
        score += 0.2

    aqi_value = (context.get("aqi") or {}).get("aqi")
    if isinstance(aqi_value, (int, float)) and aqi_value >= 151:
        factors.append("Poor air quality")
        score += 0.3

    eta = context.get("eta") or {}
    distance = eta.get("distance") or ""
    duration = eta.get("duration") or ""
    if _contains_any(duration, ["hr", "hour"]) or _contains_any(distance, ["km"]):
        try:
            distance_val = float(str(distance).split()[0])
        except Exception:
            distance_val = None
        if distance_val and distance_val >= 15:
            factors.append("Long travel distance")
            score += 0.2
    if _contains_any(duration, ["60 min", "90 min"]) or _contains_any(duration, ["hr"]):
        factors.append("Long travel time")
        score += 0.2

    news = (context.get("news") or {}).get("articles") or []
    news_risk_terms = [
        "warning",
        "alert",
        "storm",
        "flood",
        "strike",
        "protest",
        "accident",
        "earthquake",
        "wildfire",
        "security",
    ]
    for article in news[:5]:
        title = article.get("title")
        description = article.get("description")
        if _contains_any(title, news_risk_terms) or _contains_any(description, news_risk_terms):
            factors.append("Recent news indicates potential disruption")
            score += 0.2
            break

    if parsed_query:
        decision_type = parsed_query.get("decision_type")
        datetime_hint = (parsed_query.get("datetime") or "").lower()
        if decision_type in {"event", "travel"} and "tonight" in datetime_hint:
            factors.append("Late timing may affect safety or availability")
            score += 0.1

    score = min(score, 1.0)
    if score >= 0.6:
        level = "high"
    elif score >= 0.3:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "score": round(score, 2),
        "factors": factors,
        "relevant": len(factors) > 0,
    }

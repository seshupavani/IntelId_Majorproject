from backend.agent.risk_analyzer import analyze_risk


def test_risk_low_when_context_is_clean():
    context = {
        "weather": {"condition": "Clear", "temperature": 24},
        "eta": {"distance": "1.2 km", "duration": "8 min"},
        "aqi": {"aqi": 45, "category": "good"},
        "news": {"articles": []},
    }
    risk = analyze_risk(context)
    assert risk["level"] == "low"
    assert risk["relevant"] is False


def test_risk_medium_with_poor_air_and_rain():
    context = {
        "weather": {"condition": "Heavy rain", "temperature": 22},
        "eta": {"distance": "6.0 km", "duration": "30 min"},
        "aqi": {"aqi": 160, "category": "unhealthy"},
        "news": {"articles": []},
    }
    risk = analyze_risk(context)
    assert risk["level"] in {"medium", "high"}
    assert risk["relevant"] is True


def test_risk_from_news_signal():
    context = {
        "weather": {"condition": "Clear", "temperature": 26},
        "eta": {"distance": "2.0 km", "duration": "10 min"},
        "aqi": {"aqi": 60, "category": "moderate"},
        "news": {
            "articles": [
                {"title": "Flood warning issued for downtown", "description": None}
            ]
        },
    }
    risk = analyze_risk(context)
    assert risk["relevant"] is True

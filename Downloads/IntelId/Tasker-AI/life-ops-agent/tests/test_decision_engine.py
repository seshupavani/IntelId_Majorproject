from backend.agent.decision_engine import make_decision


def test_intercity_trip_prefers_bus_or_train():
    context = {
        "weather": {"condition": "Clear", "temperature": 31},
        "eta": {"distance": "163.6 km", "duration": "166 min"},
        "aqi": {"aqi": 78, "category": "moderate"},
        "news": None,
    }

    decision = make_decision(context)

    assert decision["action"] == "Take a bus or train"
    assert "Intercity distance" in decision["reason"]


def test_llm_local_transport_is_rejected_for_intercity_trip(monkeypatch):
    context = {
        "weather": {"condition": "Sunny", "temperature": 33},
        "eta": {"distance": "163.6 km", "duration": "166 min"},
        "aqi": {"aqi": 80, "category": "moderate"},
        "news": None,
    }

    monkeypatch.setattr(
        "backend.agent.decision_engine.generate_decision",
        lambda **kwargs: {
            "action": "Book a cab",
            "reason": "Fastest option",
            "confidence": 0.8,
            "model": "test-model",
        },
    )

    decision = make_decision(context, debug=True, user_query="Should I travel from Hyderabad to Karimnagar today?")

    assert decision["action"] == "Take a bus or train"
    assert decision["debug"]["llm_used"] is False

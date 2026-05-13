from fastapi.testclient import TestClient

from backend import db as db_module
from backend.agent import query_handler
from backend.api import app


def _build_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        query_handler,
        "get_weather",
        lambda destination: {
            "condition": "Clear",
            "temperature": 26,
            "source": "test",
        },
    )
    monkeypatch.setattr(
        query_handler,
        "get_eta",
        lambda source, destination: {
            "duration": "18 min",
            "distance": "4.2 km",
            "source": "test",
        },
    )
    monkeypatch.setattr(
        query_handler,
        "get_aqi",
        lambda destination: {
            "aqi": 42,
            "category": "good",
            "source": "test",
        },
    )
    return TestClient(app)


def test_auth_preferences_and_history_flow(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        status = client.get("/status")
        assert status.status_code == 200
        assert status.json()["status"] == "ok"
        assert "providers" in status.json()

        signup = client.post(
            "/auth/signup",
            json={
                "name": "Smoke User",
                "email": "smoke@example.com",
                "password": "test12345",
            },
        )
        assert signup.status_code == 201
        signup_data = signup.json()
        token = signup_data["token"]

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "smoke@example.com"

        prefs = client.put(
            "/preferences",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "budget_level": "budget",
                "comfort_priority": "balanced",
                "health_sensitivity": "high",
                "preferred_modes": ["cab", "walk"],
                "notes": "integration test",
            },
        )
        assert prefs.status_code == 200
        assert prefs.json()["preferences"]["preferred_modes"] == ["cab", "walk"]

        decision = client.post(
            "/decision",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "Should I travel from Indiranagar to MG Road today?",
                "debug": True,
            },
        )
        assert decision.status_code == 200
        decision_data = decision.json()
        assert decision_data["decision"]["action"] in {
            "Book a cab",
            "Take a bike or cab",
            "You can walk",
        }
        assert decision_data["saved_trip_id"] is not None

        history = client.get(
            "/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history.status_code == 200
        history_items = history.json()["items"]
        assert len(history_items) == 1
        assert history_items[0]["destination"] == "MG Road"

        dashboard = client.get(
            "/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert dashboard.status_code == 200
        dashboard_data = dashboard.json()
        assert dashboard_data["summary"]["total_decisions"] == 1
        assert dashboard_data["recent_history"][0]["destination"] == "MG Road"

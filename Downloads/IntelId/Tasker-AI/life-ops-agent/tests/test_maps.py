from backend.services import maps


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


def test_get_eta_uses_runtime_provider_override(monkeypatch, tmp_path):
    monkeypatch.setattr(maps, "MAPS_CACHE_PATH", str(tmp_path / "maps.json"))
    monkeypatch.setenv("ROUTING_PROVIDER", "osrm")
    monkeypatch.setattr(maps, "get_coords", lambda location, timeout=10: [77.0, 12.0])
    monkeypatch.setattr(
        maps,
        "_route_osrm",
        lambda start_coords, end_coords, timeout=10: {
            "duration": "18 min",
            "distance": "4.2 km",
            "source": "osrm",
        },
    )

    result = maps.get_eta("A", "B")

    assert result["source"] == "osrm"
    assert result["duration"] == "18 min"


def test_get_eta_falls_back_to_osrm_when_ors_has_no_routes(monkeypatch, tmp_path):
    monkeypatch.setattr(maps, "MAPS_CACHE_PATH", str(tmp_path / "maps.json"))
    monkeypatch.delenv("ROUTING_PROVIDER", raising=False)
    monkeypatch.setenv("ROUTING_FALLBACK", "osrm")
    monkeypatch.setattr(maps, "API_KEY", "real-ors-key")
    monkeypatch.setattr(maps, "get_coords", lambda location, timeout=10: [77.0, 12.0])
    monkeypatch.setattr(
        maps,
        "_request_directions",
        lambda url, params, timeout: (_Response(200), {"routes": []}),
    )
    monkeypatch.setattr(
        maps,
        "_route_osrm",
        lambda start_coords, end_coords, timeout=10: {
            "duration": "15 min",
            "distance": "3.8 km",
            "source": "osrm",
        },
    )

    result = maps.get_eta("A", "B")

    assert result["source"] == "osrm"
    assert result["distance"] == "3.8 km"


def test_get_eta_parses_ors_feature_collection(monkeypatch, tmp_path):
    monkeypatch.setattr(maps, "MAPS_CACHE_PATH", str(tmp_path / "maps.json"))
    monkeypatch.delenv("ROUTING_PROVIDER", raising=False)
    monkeypatch.setattr(maps, "API_KEY", "real-ors-key")
    monkeypatch.setattr(maps, "get_coords", lambda location, timeout=10: [77.0, 12.0])
    monkeypatch.setattr(
        maps,
        "_request_directions",
        lambda url, params, timeout: (
            _Response(200),
            {
                "features": [
                    {
                        "properties": {
                            "summary": {
                                "duration": 483.4,
                                "distance": 5330.7,
                            }
                        }
                    }
                ]
            },
        ),
    )

    result = maps.get_eta("A", "B")

    assert result["source"] == "openrouteservice"
    assert result["duration"] == "8 min"
    assert result["distance"] == "5.3 km"

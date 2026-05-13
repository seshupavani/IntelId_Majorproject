import pytest
import requests

from backend.services import weather


def test_get_weather_surfaces_request_failures_cleanly(monkeypatch, tmp_path):
    monkeypatch.setattr(weather, "API_KEY", "real-weather-key")
    monkeypatch.setattr(weather, "WEATHER_CACHE_PATH", str(tmp_path / "weather.json"))
    monkeypatch.setattr(weather, "get_coords", lambda city, timeout=10: [77.0, 12.0])

    def _raise_connection_error(url, params=None, timeout=10):
        raise requests.exceptions.ConnectionError("dns failure")

    monkeypatch.setattr(weather.requests, "get", _raise_connection_error)

    with pytest.raises(ValueError, match="Weather API request failed:"):
        weather.get_weather("Bangalore")

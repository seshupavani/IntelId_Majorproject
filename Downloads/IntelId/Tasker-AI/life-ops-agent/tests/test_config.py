from backend.agent import query_parser
from backend.config import has_configured_value, is_placeholder_value


def test_placeholder_detection_handles_example_values():
    assert is_placeholder_value("")
    assert is_placeholder_value("your_weatherapi_key")
    assert is_placeholder_value("YOUR_ORS_API_KEY")
    assert is_placeholder_value("change-me")
    assert has_configured_value("realistic-secret-123") is True


def test_query_parser_skips_llm_for_placeholder_api_key(monkeypatch):
    monkeypatch.setattr(query_parser, "OPENAI_API_KEY", "your_openai_api_key")

    parsed = query_parser.parse_query("Should I travel from Indiranagar to MG Road today?")

    assert parsed["decision_type"] == "travel"
    assert parsed["source"] == "Indiranagar"
    assert parsed["destination"] == "MG Road"

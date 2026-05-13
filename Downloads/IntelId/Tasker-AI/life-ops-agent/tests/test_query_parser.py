from backend.agent.query_parser import parse_query


def test_parse_travel_query_with_from_to():
    parsed = parse_query("Should I travel from Indiranagar to MG Road today?")
    assert parsed["decision_type"] == "travel"
    assert parsed["source"] == "Indiranagar"
    assert parsed["destination"] == "MG Road"
    assert parsed["needs"]["eta"] is True
    assert parsed["needs"]["weather"] is True
    assert parsed["datetime"] is not None


def test_parse_event_query():
    parsed = parse_query("Is it safe to attend an outdoor concert tonight in Mumbai?")
    assert parsed["decision_type"] == "event"
    assert parsed["needs"]["weather"] is True
    assert parsed["needs"]["news"] is True


def test_parse_daily_query_without_location():
    parsed = parse_query("Should I go to the office today?")
    assert parsed["decision_type"] in {"daily", "travel"}
    assert parsed["needs"]["news"] is True or parsed["needs"]["weather"] is True


def test_parse_travel_query_with_soft_intro():
    parsed = parse_query("I want to check if I can travel to gokaraju rangaraju institute today")
    assert parsed["decision_type"] == "travel"
    assert parsed["destination"] == "gokaraju rangaraju institute"
    assert parsed["needs"]["weather"] is True


def test_parse_travel_query_with_destination_and_from():
    parsed = parse_query("should I visit gokaraju rangaraju institute today from alwal?")
    assert parsed["decision_type"] == "travel"
    assert parsed["destination"] == "gokaraju rangaraju institute"
    assert parsed["source"] == "alwal"


def test_parse_travel_query_with_travel_to_from():
    parsed = parse_query("Should I travel to bhavans Sri rama krishna vidyalaya from alwal now?")
    assert parsed["decision_type"] == "travel"
    assert parsed["destination"] == "bhavans Sri rama krishna vidyalaya"
    assert parsed["source"] == "alwal"

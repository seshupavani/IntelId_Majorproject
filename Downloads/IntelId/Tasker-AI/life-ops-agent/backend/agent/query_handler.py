from concurrent.futures import ThreadPoolExecutor
import logging

from backend.agent.query_parser import parse_query
from backend.agent.risk_analyzer import analyze_risk
from backend.agent.decision_engine import make_decision
from backend.agent.action_planner import plan_action
from backend.services.weather import get_weather
from backend.services.maps import get_eta
from backend.services.aqi import get_aqi
from backend.services.news import get_news, NEWS_API_CONFIGURED

logger = logging.getLogger(__name__)


def get_decision_from_query(query, debug=False):
    parsed = parse_query(query)

    needs = parsed.get("needs") or {}
    source = parsed.get("source")
    destination = parsed.get("destination")
    topic = parsed.get("topic") or destination

    context = {
        "weather": None,
        "eta": None,
        "aqi": None,
        "news": None,
    }
    sources = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        if needs.get("weather") and destination:
            futures["weather"] = pool.submit(get_weather, destination)
        if needs.get("eta") and source and destination:
            futures["eta"] = pool.submit(get_eta, source, destination)
        if needs.get("aqi") and destination:
            futures["aqi"] = pool.submit(get_aqi, destination)
        if needs.get("news") and topic and NEWS_API_CONFIGURED:
            futures["news"] = pool.submit(get_news, topic)

        for key, future in futures.items():
            try:
                context[key] = future.result()
                sources[key] = (context[key] or {}).get("source")
            except Exception as exc:
                logger.warning("%s fetch failed: %s", key, exc)
                context[key] = None

    risk = analyze_risk(context, parsed_query=parsed)
    if parsed.get("decision_type") == "travel" and not source:
        decision = {
            "action": "Provide your starting location",
            "reason": "I need your starting point to estimate distance and travel time.",
            "confidence": 0.2,
        }
        plan = {"type": "none", "link": None, "label": "No action"}
    elif parsed.get("decision_type") == "travel" and not destination:
        decision = {
            "action": "Provide your destination",
            "reason": "I need a destination to fetch live travel data.",
            "confidence": 0.2,
        }
        plan = {"type": "none", "link": None, "label": "No action"}
    else:
        decision = make_decision(
            context,
            debug=debug,
            user_query=query,
            news=context.get("news"),
            risk=risk,
        )
        plan = plan_action(decision, destination=destination)

    return {
        "query": query,
        "interpretation": parsed,
        "context": context,
        "sources": sources,
        "risk": risk,
        "decision": decision,
        "plan": plan,
    }

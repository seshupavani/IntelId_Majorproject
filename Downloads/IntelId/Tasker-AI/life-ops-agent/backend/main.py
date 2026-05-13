import argparse
import json
import os
import sys

from backend.agent.context_builder import get_context
from backend.agent.query_handler import get_decision_from_query
from backend.agent.decision_engine import make_decision
from backend.agent.action_planner import plan_action
from backend.services.weather import purge_weather_cache
from backend.services.maps import purge_geocode_cache, clear_route_cache


def run(source, destination):
    context = get_context(source, destination)
    decision = make_decision(context, news=context.get("news"))
    plan = plan_action(decision, destination=destination)
    return {
        "context": context,
        "decision": decision,
        "plan": plan,
    }


def run_query(query, debug=False):
    return get_decision_from_query(query, debug=debug)

def _print_table(result):
    context = result["context"]
    decision = result["decision"]
    plan = result["plan"]

    lines = []
    lines.append("Context")
    weather = context.get("weather") or {}
    eta = context.get("eta") or {}
    lines.append(f"- Weather: {weather.get('condition')} ({weather.get('temperature')}°C)")
    lines.append(f"- ETA: {eta.get('duration')} ({eta.get('distance')})")
    if context.get("aqi") is not None:
        lines.append(f"- AQI: {context['aqi'].get('aqi')} ({context['aqi'].get('category')})")
    if context.get("news"):
        lines.append("- News: available")
    lines.append("")
    lines.append("Decision")
    lines.append(f"- Action: {decision.get('action')}")
    lines.append(f"- Reason: {decision.get('reason')}")
    lines.append(f"- Confidence: {decision.get('confidence')}")
    lines.append("")
    lines.append("Plan")
    lines.append(f"- Type: {plan.get('type')}")
    lines.append(f"- Link: {plan.get('link')}")
    print("\n".join(lines))


def main(argv):
    parser = argparse.ArgumentParser(description="Life Ops Agent CLI")
    parser.add_argument("source", nargs="?", help="Origin location (address or lat,lon)")
    parser.add_argument("destination", nargs="?", help="Destination location (address or lat,lon)")
    parser.add_argument("--query", help="Natural-language decision query")
    parser.add_argument(
        "--provider",
        choices=["ors", "osrm", "google"],
        help="Routing provider override",
    )
    parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument("--quiet", action="store_true", help="Suppress output on success")
    parser.add_argument("--purge-cache", metavar="LOCATION", help="Clear cached entries for a location")
    parser.add_argument("--clear-route-cache", action="store_true", help="Clear all cached routes")
    args = parser.parse_args(argv[1:])

    if args.provider:
        os.environ["ROUTING_PROVIDER"] = args.provider
    if args.purge_cache:
        removed_weather = purge_weather_cache(args.purge_cache)
        removed_geocode = purge_geocode_cache(args.purge_cache)
        removed_routes = False
        if args.clear_route_cache:
            removed_routes = clear_route_cache()
        print(f"Cache cleared: weather={removed_weather}, geocode={removed_geocode}, routes={removed_routes}")
        return 0
    if args.clear_route_cache:
        removed_routes = clear_route_cache()
        print(f"Cache cleared: routes={removed_routes}")
        return 0

    if args.query:
        try:
            result = run_query(args.query, debug=False)
        except Exception as exc:
            print(f"Error: {exc}")
            return 1
        if args.quiet:
            return 0
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            _print_table(result)
        return 0

    if not args.source or not args.destination:
        parser.print_usage()
        return 2

    try:
        result = run(args.source, args.destination)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    if args.quiet:
        return 0

    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

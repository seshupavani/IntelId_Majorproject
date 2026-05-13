from urllib.parse import quote_plus


def _build_uber_link(destination):
    if not destination:
        return "https://m.uber.com/ul/"
    encoded = quote_plus(destination)
    return (
        "https://m.uber.com/ul/?action=setPickup"
        f"&dropoff[formatted_address]={encoded}"
    )


def plan_action(decision, destination=None):
    action = ""
    if isinstance(decision, dict):
        action = decision.get("action", "") or ""
    action_lower = action.lower()

    if "flight" in action_lower:
        return {
            "type": "flight",
            "link": "https://www.google.com/flights",
            "label": "Search Flights",
        }

    if "bus" in action_lower and "train" in action_lower:
        return {
            "type": "intercity",
            "link": "https://www.google.com/travel/",
            "label": "Plan Intercity Trip",
        }

    if "train" in action_lower:
        return {
            "type": "train",
            "link": "https://www.irctc.co.in",
            "label": "Book Train",
        }

    if "bus" in action_lower:
        return {
            "type": "bus",
            "link": "https://www.redbus.in/",
            "label": "Find Buses",
        }

    if "cab" in action_lower:
        return {
            "type": "ride",
            "link": _build_uber_link(destination),
            "label": "Book Uber",
        }

    # Handle bike recommendations
    if "bike" in action_lower or "bicycle" in action_lower:
        return {
            "type": "bike",
            "link": None,
            "label": "Use Bike",
        }

    # Handle walk recommendations
    if "walk" in action_lower:
        return {
            "type": "walk",
            "link": None,
            "label": "Walk",
        }

    return {
        "type": "none",
        "link": None,
        "label": "No action",
    }

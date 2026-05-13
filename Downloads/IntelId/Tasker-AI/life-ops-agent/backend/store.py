import json

from backend.auth import hash_password
from backend.db import get_connection


DEFAULT_PREFERRED_MODES = ["cab", "bike", "walk", "train"]


def _parse_modes(value):
    if not value:
        return DEFAULT_PREFERRED_MODES[:]
    if isinstance(value, list):
        return [item for item in value if item]
    return [item for item in str(value).split(",") if item]


def _normalize_user(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _normalize_preferences(row):
    if row is None:
        return {
            "budget_level": "balanced",
            "comfort_priority": "balanced",
            "health_sensitivity": "medium",
            "preferred_modes": DEFAULT_PREFERRED_MODES[:],
            "home_location": None,
            "work_location": None,
            "notes": None,
        }
    return {
        "budget_level": row["budget_level"],
        "comfort_priority": row["comfort_priority"],
        "health_sensitivity": row["health_sensitivity"],
        "preferred_modes": _parse_modes(row["preferred_modes"]),
        "home_location": row["home_location"],
        "work_location": row["work_location"],
        "notes": row["notes"],
    }


def create_user(name, email, password):
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        raise ValueError("Email is required")
    if not name or not name.strip():
        raise ValueError("Name is required")

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
        if existing:
            raise ValueError("An account with this email already exists")

        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (name.strip(), normalized_email, hash_password(password)),
        )
        user_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id,
                budget_level,
                comfort_priority,
                health_sensitivity,
                preferred_modes
            )
            VALUES (?, 'balanced', 'balanced', 'medium', ?)
            """,
            (user_id, ",".join(DEFAULT_PREFERRED_MODES)),
        )
        conn.commit()
        return get_user_by_id(user_id)
    finally:
        conn.close()


def get_user_record_by_email(email):
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        return _normalize_user(row)
    finally:
        conn.close()


def get_preferences(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()
        return _normalize_preferences(row)
    finally:
        conn.close()


def upsert_preferences(user_id, payload):
    current = get_preferences(user_id)
    updated = {
        "budget_level": payload.get("budget_level") or current["budget_level"],
        "comfort_priority": payload.get("comfort_priority") or current["comfort_priority"],
        "health_sensitivity": payload.get("health_sensitivity") or current["health_sensitivity"],
        "preferred_modes": payload.get("preferred_modes") or current["preferred_modes"],
        "home_location": payload.get("home_location"),
        "work_location": payload.get("work_location"),
        "notes": payload.get("notes"),
    }

    if updated["home_location"] is None:
        updated["home_location"] = current["home_location"]
    if updated["work_location"] is None:
        updated["work_location"] = current["work_location"]
    if updated["notes"] is None:
        updated["notes"] = current["notes"]

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id,
                budget_level,
                comfort_priority,
                health_sensitivity,
                preferred_modes,
                home_location,
                work_location,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                budget_level = excluded.budget_level,
                comfort_priority = excluded.comfort_priority,
                health_sensitivity = excluded.health_sensitivity,
                preferred_modes = excluded.preferred_modes,
                home_location = excluded.home_location,
                work_location = excluded.work_location,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                updated["budget_level"],
                updated["comfort_priority"],
                updated["health_sensitivity"],
                ",".join(_parse_modes(updated["preferred_modes"])),
                updated["home_location"],
                updated["work_location"],
                updated["notes"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_preferences(user_id)


def save_trip_decision(
    user_id,
    query,
    interpretation,
    context,
    risk,
    decision,
    plan,
):
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO trip_decisions (
                user_id,
                query,
                source,
                destination,
                decision_type,
                context_json,
                risk_json,
                decision_json,
                plan_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                query,
                (interpretation or {}).get("source"),
                (interpretation or {}).get("destination"),
                (interpretation or {}).get("decision_type"),
                json.dumps(context),
                json.dumps(risk),
                json.dumps(decision),
                json.dumps(plan),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _normalize_trip_row(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "query": row["query"],
        "source": row["source"],
        "destination": row["destination"],
        "decision_type": row["decision_type"],
        "context": json.loads(row["context_json"]),
        "risk": json.loads(row["risk_json"]),
        "decision": json.loads(row["decision_json"]),
        "plan": json.loads(row["plan_json"]),
        "created_at": row["created_at"],
    }


def list_trip_history(user_id, limit=20):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM trip_decisions
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (int(user_id), int(limit)),
        ).fetchall()
        return [_normalize_trip_row(row) for row in rows]
    finally:
        conn.close()


def get_trip_history_item(user_id, trip_id):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM trip_decisions
            WHERE user_id = ? AND id = ?
            """,
            (int(user_id), int(trip_id)),
        ).fetchone()
        return _normalize_trip_row(row)
    finally:
        conn.close()


def get_dashboard(user_id):
    history = list_trip_history(user_id, limit=100)
    total_decisions = len(history)
    action_breakdown = {}
    risk_breakdown = {"low": 0, "medium": 0, "high": 0}

    for item in history:
        action = ((item.get("decision") or {}).get("action") or "Unknown").strip()
        action_breakdown[action] = action_breakdown.get(action, 0) + 1

        risk_level = ((item.get("risk") or {}).get("level") or "low").strip().lower()
        if risk_level not in risk_breakdown:
            risk_breakdown[risk_level] = 0
        risk_breakdown[risk_level] += 1

    recent_destinations = []
    seen = set()
    for item in history:
        destination = item.get("destination")
        if destination and destination not in seen:
            recent_destinations.append(destination)
            seen.add(destination)
        if len(recent_destinations) >= 5:
            break

    latest = history[0] if history else None
    return {
        "summary": {
            "total_decisions": total_decisions,
            "high_risk_decisions": risk_breakdown.get("high", 0),
            "recent_destinations": recent_destinations,
            "last_decision_at": latest.get("created_at") if latest else None,
        },
        "action_breakdown": action_breakdown,
        "risk_breakdown": risk_breakdown,
        "recent_history": history[:5],
    }

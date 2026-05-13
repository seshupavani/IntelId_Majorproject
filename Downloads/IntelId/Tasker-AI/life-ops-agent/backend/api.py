from contextlib import asynccontextmanager
import logging
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.auth import create_token, decode_token, verify_password
from backend.config import has_configured_value
from backend.agent.context_builder import get_context
from backend.agent.decision_engine import make_decision
from backend.agent.action_planner import plan_action
from backend.agent.query_handler import get_decision_from_query
from backend.db import init_db
from backend.schemas import (
    DecisionRequest,
    LoginRequest,
    PreferencesUpdateRequest,
    SignupRequest,
)
from backend.store import (
    create_user,
    get_dashboard,
    get_preferences,
    get_trip_history_item,
    get_user_by_id,
    get_user_record_by_email,
    list_trip_history,
    save_trip_decision,
    upsert_preferences,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("life_ops_api")


def _get_provider_status():
    routing_provider = os.getenv("ROUTING_PROVIDER", "ors").lower()
    routing_ready = routing_provider == "osrm"
    if routing_provider == "ors":
        routing_ready = has_configured_value(os.getenv("ORS_API_KEY"))
    elif routing_provider == "google":
        routing_ready = has_configured_value(os.getenv("GOOGLE_MAPS_API_KEY"))

    return {
        "weather": has_configured_value(os.getenv("WEATHERAPI_KEY")),
        "routing": {
            "provider": routing_provider,
            "configured": routing_ready,
        },
        "aqi": True,
        "news": has_configured_value(os.getenv("NEWS_API_KEY")),
        "openai": has_configured_value(os.getenv("OPENAI_API_KEY")),
        "auth": has_configured_value(os.getenv("AUTH_SECRET")),
    }


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Life Ops Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_email(email):
    normalized = (email or "").strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Please provide a valid email address")
    return normalized


def _extract_token(authorization: Optional[str]):
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return token.strip()


def _resolve_optional_user(authorization: Optional[str]):
    token = _extract_token(authorization)
    if not token:
        return None
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _resolve_current_user(authorization: Optional[str]):
    user = _resolve_optional_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _build_auth_response(user):
    return {
        "token": create_token(user["id"]),
        "user": user,
        "preferences": get_preferences(user["id"]),
    }


def _run_decision_query(query, debug=False, user=None):
    result = get_decision_from_query(query, debug=debug)
    saved_trip_id = None
    if user:
        saved_trip_id = save_trip_decision(
            user_id=user["id"],
            query=query,
            interpretation=result.get("interpretation"),
            context=result.get("context"),
            risk=result.get("risk"),
            decision=result.get("decision"),
            plan=result.get("plan"),
        )
    result["saved_trip_id"] = saved_trip_id
    return result


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Life Ops Agent API is running.",
        "endpoints": [
            "/context",
            "/decision",
            "/auth/signup",
            "/auth/login",
            "/auth/me",
            "/preferences",
            "/history",
            "/dashboard",
            "/docs",
        ],
    }


@app.get("/status")
def status_endpoint():
    return {
        "status": "ok",
        "providers": _get_provider_status(),
    }


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest):
    try:
        user = create_user(
            name=payload.name,
            email=_validate_email(payload.email),
            password=payload.password,
        )
        return _build_auth_response(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login")
def login(payload: LoginRequest):
    email = _validate_email(payload.email)
    record = get_user_record_by_email(email)
    if not record or not verify_password(payload.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user = get_user_by_id(record["id"])
    return _build_auth_response(user)


@app.get("/auth/me")
def me(authorization: Optional[str] = Header(default=None)):
    user = _resolve_current_user(authorization)
    return {
        "user": user,
        "preferences": get_preferences(user["id"]),
    }


@app.get("/preferences")
def preferences(authorization: Optional[str] = Header(default=None)):
    user = _resolve_current_user(authorization)
    return get_preferences(user["id"])


@app.put("/preferences")
def update_preferences(
    payload: PreferencesUpdateRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _resolve_current_user(authorization)
    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    updated = upsert_preferences(user["id"], payload_data)
    return {
        "message": "Preferences updated",
        "preferences": updated,
    }


@app.get("/history")
def history(
    limit: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(default=None),
):
    user = _resolve_current_user(authorization)
    return {
        "items": list_trip_history(user["id"], limit=limit),
    }


@app.get("/history/{trip_id}")
def history_detail(trip_id: int, authorization: Optional[str] = Header(default=None)):
    user = _resolve_current_user(authorization)
    item = get_trip_history_item(user["id"], trip_id)
    if not item:
        raise HTTPException(status_code=404, detail="Trip history item not found")
    return item


@app.get("/dashboard")
def dashboard(authorization: Optional[str] = Header(default=None)):
    user = _resolve_current_user(authorization)
    return get_dashboard(user["id"])


@app.get("/context")
def get_context_endpoint(
    source: str = Query(..., description="Origin address or 'lat,lon'"),
    destination: str = Query(..., description="Destination address or 'lat,lon'"),
    debug: bool = Query(False, description="Include decision debug info"),
):
    try:
        logger.info("request source=%s destination=%s", source, destination)
        context = get_context(source, destination)
        logger.info("context %s", context)
        decision = make_decision(context, debug=debug, news=context.get("news"))
        logger.info("decision %s", decision)
        plan = plan_action(decision, destination=destination)
        return {
            "context": context,
            "decision": decision,
            "plan": plan,
        }
    except Exception as exc:
        logger.exception("error source=%s destination=%s", source, destination)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/decision")
def get_decision_endpoint(
    query: str = Query(..., description="Natural-language decision query"),
    debug: bool = Query(False, description="Include decision debug info"),
    authorization: Optional[str] = Header(default=None),
):
    try:
        logger.info("request query=%s", query)
        user = _resolve_optional_user(authorization)
        return _run_decision_query(query, debug=debug, user=user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("error query=%s", query)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/decision")
def create_decision(
    payload: DecisionRequest,
    authorization: Optional[str] = Header(default=None),
):
    try:
        user = _resolve_current_user(authorization)
        logger.info("request query=%s user=%s", payload.query, user["id"])
        return _run_decision_query(payload.query, debug=payload.debug, user=user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("error query=%s", payload.query)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def run():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()

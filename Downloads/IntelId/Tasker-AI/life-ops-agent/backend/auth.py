import base64
import hashlib
import hmac
import json
import os
import secrets
import time


TOKEN_TTL_SEC = int(os.getenv("AUTH_TOKEN_TTL_SEC", str(60 * 60 * 24 * 7)))
PASSWORD_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "120000"))
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-life-ops-secret-change-me")


def _b64url_encode(value):
    raw = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def hash_password(password):
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        f"{_b64url_encode(salt)}${_b64url_encode(digest)}"
    )


def verify_password(password, password_hash):
    try:
        algorithm, iterations, salt, digest = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _b64url_decode(salt),
        int(iterations),
    )
    return hmac.compare_digest(_b64url_encode(candidate), digest)


def create_token(user_id):
    payload = {
        "sub": int(user_id),
        "exp": int(time.time()) + TOKEN_TTL_SEC,
    }
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")))
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def decode_token(token):
    if not token or "." not in token:
        raise ValueError("Invalid token")
    payload_part, signature_part = token.split(".", 1)
    expected_signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_part):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_part))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Invalid token payload")
    return payload

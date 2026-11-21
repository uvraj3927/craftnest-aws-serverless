import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import PBKDF2_ITERATIONS, SESSION_SECRET, SESSION_TTL_SECONDS

_HASH_NAME = "sha256"
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        _HASH_NAME, password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(derived).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, expected_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            _HASH_NAME, password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def create_session_token(user: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": user["user_id"],
        "email": user["email"],
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64url(
        hmac.new(SESSION_SECRET, body.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{body}.{signature}"


def verify_session_token(token: str) -> dict | None:
    try:
        body, supplied_signature = token.split(".", 1)
        expected_signature = _b64url(
            hmac.new(SESSION_SECRET, body.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) <= int(time.time()):
            return None
        if not payload.get("sub") or not payload.get("email"):
            return None
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

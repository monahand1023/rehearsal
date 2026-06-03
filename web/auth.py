import hmac
import os

from itsdangerous import URLSafeTimedSerializer

COOKIE_NAME = "rehearsal_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_SALT = "rehearsal-gate"


def gate_enabled() -> bool:
    return bool(os.environ.get("REHEARSAL_ACCESS_CODE"))


def check_code(submitted: str) -> bool:
    secret = os.environ.get("REHEARSAL_ACCESS_CODE")
    if not secret:
        return False
    return hmac.compare_digest(submitted or "", secret)


def _serializer() -> URLSafeTimedSerializer:
    key = os.environ.get("REHEARSAL_SESSION_SECRET", "dev-insecure-secret")
    return URLSafeTimedSerializer(key, salt=_SALT)


def make_token() -> str:
    return _serializer().dumps("ok")


def valid_token(token) -> bool:
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=COOKIE_MAX_AGE)
        return True
    except Exception:  # bad signature, expired, or malformed → not valid
        return False


def unlock_delay() -> float:
    return float(os.environ.get("REHEARSAL_UNLOCK_DELAY", "3.0"))


def cookie_secure() -> bool:
    return os.environ.get("REHEARSAL_COOKIE_SECURE", "false").lower() == "true"

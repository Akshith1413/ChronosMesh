"""
ChronosMesh API – auth utilities
JWT token creation + verification, bcrypt password hashing, role-based access control.

Configuration (environment)
---------------------------
JWT_SECRET_KEY / JWT_SECRET_ARN   signing key (ARN = AWS Secrets Manager secret holding the key)
ENVIRONMENT                       ``production`` makes a weak/default secret a startup error
ENABLE_DEMO_USERS                 built-in demo accounts; default on locally, **off in production**
USERS_JSON / USERS_SECRET_ARN     real accounts: {"alice": {"password": "...", "role": "admin"}}
                                  (``password`` may be a bcrypt hash)
AUTH_USERS + AUTH_PASSWORD_<NAME> ``admin:admin,ana:analyst`` (user:role list) with one password env var per
                                  user -- the shape ECS/Kubernetes secret injection produces
ACCESS_TOKEN_EXPIRE_MINUTES       token lifetime (default 1440 locally, 60 in production)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger("chronosmesh.auth")

# ── Role-Based Access Control (RBAC) ──────────────────────────────────────────
ROLE_VIEWER = "viewer"
ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"

ROLE_HIERARCHY = {
    ROLE_VIEWER: 1,
    ROLE_ANALYST: 2,
    ROLE_ADMIN: 3,
}

_DEV_SECRET = "chronosmesh-dev-only-secret-do-not-use-in-production"
_KNOWN_WEAK = {
    _DEV_SECRET,
    "chronosmesh-secret-key-guru-2024-xQ9mP2vL",       # value that used to be committed to the repo
    "chronosmesh-prod-k8s-cluster-secret-key-32chars",  # ditto (k8s ConfigMap)
    "change-me", "secret", "",
}
ALGORITHM = "HS256"


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "local").lower() == "production"


def _secretsmanager_json(arn: str) -> str:
    import boto3

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    return boto3.client("secretsmanager", region_name=region).get_secret_value(SecretId=arn)["SecretString"]


def _load_secret_key() -> str:
    key = os.getenv("JWT_SECRET_KEY")
    arn = os.getenv("JWT_SECRET_ARN")
    if not key and arn:
        raw = _secretsmanager_json(arn)
        try:
            parsed = json.loads(raw)
            key = parsed.get("jwt_secret") or parsed.get("secret") if isinstance(parsed, dict) else raw
        except json.JSONDecodeError:
            key = raw
    if _is_production():
        if not key or key in _KNOWN_WEAK or len(key) < 32:
            raise RuntimeError(
                "Refusing to start: ENVIRONMENT=production requires a JWT secret of >= 32 characters "
                "supplied via JWT_SECRET_KEY or JWT_SECRET_ARN (the built-in development default is not allowed)."
            )
        return key
    if not key:
        logger.warning("JWT_SECRET_KEY not set: using the development secret (never do this in production)")
        return _DEV_SECRET
    return key


SECRET_KEY = _load_secret_key()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60" if _is_production() else "1440"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _hash_if_plain(password: str) -> str:
    return password if password.startswith("$2") else pwd_context.hash(password)


def _build_users() -> Dict[str, dict]:
    users: Dict[str, dict] = {}

    demo_default = "false" if _is_production() else "true"
    if os.getenv("ENABLE_DEMO_USERS", demo_default).lower() in ("1", "true", "yes"):
        users.update({
            "guru": {
                "username": "guru", "full_name": "Guru Sai Prasad Reddy", "email": "guru@chronosmesh.dev",
                "role": ROLE_ADMIN, "hashed_password": pwd_context.hash("chronosmesh"),
            },
            "analyst": {
                "username": "analyst", "full_name": "Security & Causal Analyst", "email": "analyst@chronosmesh.dev",
                "role": ROLE_ANALYST, "hashed_password": pwd_context.hash("analyst123"),
            },
            "demo": {
                "username": "demo", "full_name": "Demo Viewer", "email": "demo@chronosmesh.dev",
                "role": ROLE_VIEWER, "hashed_password": pwd_context.hash("demo123"),
            },
        })

    raw = os.getenv("USERS_JSON")
    arn = os.getenv("USERS_SECRET_ARN")
    if not raw and arn:
        raw = _secretsmanager_json(arn)
    if raw:
        for name, spec in json.loads(raw).items():
            role = str(spec.get("role", ROLE_VIEWER)).lower()
            if role not in ROLE_HIERARCHY:
                raise RuntimeError(f"user {name!r} has unknown role {role!r}")
            users[name] = {
                "username": name, "full_name": spec.get("full_name", name),
                "email": spec.get("email", f"{name}@chronosmesh.local"),
                "role": role, "hashed_password": _hash_if_plain(spec["password"]),
            }

    listed = os.getenv("AUTH_USERS", "")
    for entry in [e.strip() for e in listed.split(",") if e.strip()]:
        name, _, role = entry.partition(":")
        role = (role or ROLE_VIEWER).lower()
        if role not in ROLE_HIERARCHY:
            raise RuntimeError(f"user {name!r} has unknown role {role!r}")
        password = os.getenv(f"AUTH_PASSWORD_{name.upper().replace('-', '_')}")
        if not password:
            raise RuntimeError(f"AUTH_USERS lists {name!r} but AUTH_PASSWORD_{name.upper()} is not set")
        users[name] = {
            "username": name, "full_name": name.capitalize(), "email": f"{name}@chronosmesh.local",
            "role": role, "hashed_password": _hash_if_plain(password),
        }

    if _is_production() and not users:
        raise RuntimeError("Refusing to start: no users configured (set USERS_JSON or USERS_SECRET_ARN).")
    return users


_USERS = _build_users()


# ── Helpers ─────────────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_user(username: str) -> Optional[dict]:
    return _USERS.get(username)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user(username)
    if user and verify_password(password, user["hashed_password"]):
        return user
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── FastAPI dependencies ────────────────────────────────────────────────────────
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    user = get_user(username)
    if not user:
        raise exc
    return user


def require_role(min_role: str):
    """Enforce hierarchical RBAC on endpoint access."""
    def _role_checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", ROLE_VIEWER).lower()
        user_rank = ROLE_HIERARCHY.get(user_role, 0)
        required_rank = ROLE_HIERARCHY.get(min_role.lower(), 1)
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Requires '{min_role.upper()}', found '{user_role.upper()}'",
            )
        return user
    return _role_checker


def demo_users_enabled() -> bool:
    """True when the built-in demo accounts exist (the UI then offers one-click demo login)."""
    return "guru" in _USERS and "demo" in _USERS and _USERS["guru"].get("email") == "guru@chronosmesh.dev"

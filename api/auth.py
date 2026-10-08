"""
ChronosMesh API – auth utilities
JWT token creation + verification, bcrypt password hashing.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# ── Config ─────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "chronosmesh-secret-key-guru-2024-xQ9mP2vL")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Role-Based Access Control (RBAC) ──────────────────────────────────────────
ROLE_VIEWER = "viewer"
ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"

ROLE_HIERARCHY = {
    ROLE_VIEWER: 1,
    ROLE_ANALYST: 2,
    ROLE_ADMIN: 3,
}

# ── Demo user store (replace with DB integration when Surya's layer is ready) ──
_USERS = {
    "guru": {
        "username": "guru",
        "full_name": "Guru Sai Prasad Reddy",
        "email": "guru@chronosmesh.dev",
        "role": ROLE_ADMIN,
        "hashed_password": pwd_context.hash("chronosmesh"),
    },
    "analyst": {
        "username": "analyst",
        "full_name": "Security & Causal Analyst",
        "email": "analyst@chronosmesh.dev",
        "role": ROLE_ANALYST,
        "hashed_password": pwd_context.hash("analyst123"),
    },
    "demo": {
        "username": "demo",
        "full_name": "Demo Viewer",
        "email": "demo@chronosmesh.dev",
        "role": ROLE_VIEWER,
        "hashed_password": pwd_context.hash("demo123"),
    },
}


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


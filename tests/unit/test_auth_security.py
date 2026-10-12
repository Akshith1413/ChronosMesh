"""Auth hardening: no committed/default secrets in production, demo users off, strong config only."""

import json

import pytest

import api.auth as auth


def test_production_refuses_missing_or_weak_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_ARN", raising=False)
    with pytest.raises(RuntimeError, match="JWT secret"):
        auth._load_secret_key()
    for weak in ("change-me", "short", auth._DEV_SECRET, "chronosmesh-secret-key-guru-2024-xQ9mP2vL"):
        monkeypatch.setenv("JWT_SECRET_KEY", weak)
        with pytest.raises(RuntimeError):
            auth._load_secret_key()
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    assert auth._load_secret_key() == "x" * 40


def test_local_mode_falls_back_to_dev_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    assert auth._load_secret_key() == auth._DEV_SECRET


def test_demo_users_are_off_by_default_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENABLE_DEMO_USERS", raising=False)
    monkeypatch.setenv("USERS_JSON", json.dumps({"ops": {"password": "s3cret-pass", "role": "admin"}}))
    users = auth._build_users()
    assert set(users) == {"ops"} and users["ops"]["role"] == "admin"
    assert users["ops"]["hashed_password"].startswith("$2") and users["ops"]["hashed_password"] != "s3cret-pass"


def test_production_without_any_user_refuses_to_start(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("USERS_JSON", raising=False)
    monkeypatch.delenv("USERS_SECRET_ARN", raising=False)
    monkeypatch.delenv("ENABLE_DEMO_USERS", raising=False)
    with pytest.raises(RuntimeError, match="no users"):
        auth._build_users()


def test_demo_users_can_be_forced_on_and_unknown_roles_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENABLE_DEMO_USERS", "true")
    monkeypatch.delenv("USERS_JSON", raising=False)
    assert {"guru", "analyst", "demo"} <= set(auth._build_users())
    monkeypatch.setenv("USERS_JSON", json.dumps({"x": {"password": "p", "role": "root"}}))
    with pytest.raises(RuntimeError, match="unknown role"):
        auth._build_users()


def test_precomputed_bcrypt_hashes_are_accepted(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    hashed = auth.pwd_context.hash("pw")
    monkeypatch.setenv("USERS_JSON", json.dumps({"bob": {"password": hashed, "role": "viewer"}}))
    users = auth._build_users()
    assert users["bob"]["hashed_password"] == hashed and auth.verify_password("pw", users["bob"]["hashed_password"])


def test_cors_wildcard_is_refused(monkeypatch):
    from api.main import _cors_origins
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, *")
    with pytest.raises(RuntimeError, match="explicit origins"):
        _cors_origins()
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example/")
    assert "https://a.example" in _cors_origins()
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert _cors_origins() == ["https://a.example"]        # no localhost origins in production


def test_auth_users_from_injected_password_env_vars(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("USERS_JSON", raising=False)
    monkeypatch.delenv("ENABLE_DEMO_USERS", raising=False)
    monkeypatch.setenv("AUTH_USERS", "admin:admin, ana:analyst,viewer-1:viewer")
    monkeypatch.setenv("AUTH_PASSWORD_ADMIN", "pw-admin")
    monkeypatch.setenv("AUTH_PASSWORD_ANA", "pw-ana")
    monkeypatch.setenv("AUTH_PASSWORD_VIEWER_1", "pw-v")
    users = auth._build_users()
    assert {u: users[u]["role"] for u in users} == {"admin": "admin", "ana": "analyst", "viewer-1": "viewer"}
    assert auth.verify_password("pw-ana", users["ana"]["hashed_password"])
    assert "guru" not in users                                  # demo accounts stay off in production


def test_auth_users_requires_a_password_and_a_valid_role(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("AUTH_USERS", "bob:viewer")
    monkeypatch.delenv("AUTH_PASSWORD_BOB", raising=False)
    with pytest.raises(RuntimeError, match="AUTH_PASSWORD_BOB"):
        auth._build_users()
    monkeypatch.setenv("AUTH_PASSWORD_BOB", "x")
    monkeypatch.setenv("AUTH_USERS", "bob:superuser")
    with pytest.raises(RuntimeError, match="unknown role"):
        auth._build_users()

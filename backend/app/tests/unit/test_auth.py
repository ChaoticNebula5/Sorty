from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth
from app.core.auth import require_admin_auth, require_api_key
from app.core.config import get_settings


def test_require_api_key_rejects_missing_key() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "missing_api_key"


def test_require_api_key_rejects_invalid_key() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_api_key("wrong-key")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "invalid_api_key"


def test_require_api_key_accepts_valid_key_when_legacy_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="local",
            enable_legacy_api_key=True,
            app_api_key="demo-secret",
            admin_token="owner-secret",
        ),
    )

    assert require_api_key("demo-secret") is None


def test_require_admin_auth_rejects_missing_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_admin_auth(credentials=None, api_key=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "missing_admin_token"


def test_require_admin_auth_rejects_invalid_bearer_token() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong")

    with pytest.raises(HTTPException) as exc_info:
        require_admin_auth(credentials=credentials, api_key=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "invalid_admin_token"


def test_require_admin_auth_accepts_valid_bearer_token() -> None:
    settings = get_settings()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=settings.admin_token,
    )

    assert require_admin_auth(credentials=credentials, api_key=None) is None


def test_require_admin_auth_rejects_legacy_api_key_by_default() -> None:
    settings = get_settings()

    with pytest.raises(HTTPException) as exc_info:
        require_admin_auth(credentials=None, api_key=settings.app_api_key)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "invalid_admin_token"


def test_require_admin_auth_accepts_legacy_api_key_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="local",
            enable_legacy_api_key=True,
            app_api_key="demo-secret",
            admin_token="owner-secret",
        ),
    )

    assert require_admin_auth(credentials=None, api_key="demo-secret") is None


def test_require_admin_auth_rejects_legacy_api_key_outside_local(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            enable_legacy_api_key=True,
            app_api_key="demo-secret",
            admin_token="owner-secret",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        require_admin_auth(credentials=None, api_key="demo-secret")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "invalid_admin_token"

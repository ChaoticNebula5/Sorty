import pytest
from fastapi import HTTPException

from app.core.auth import require_api_key
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


def test_require_api_key_accepts_valid_key() -> None:
    settings = get_settings()

    assert require_api_key(settings.app_api_key) is None

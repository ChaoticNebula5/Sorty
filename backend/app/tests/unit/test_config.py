import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reject_placeholder_admin_token_outside_local() -> None:
    with pytest.raises(ValidationError, match="ADMIN_TOKEN must be changed"):
        Settings(app_env="production", admin_token="change-me-before-hosting")


def test_settings_reject_missing_admin_token_in_production() -> None:
    with pytest.raises(ValidationError, match="ADMIN_TOKEN must be set"):
        Settings(app_env="production", admin_token="")


def test_settings_reject_legacy_api_key_outside_local() -> None:
    with pytest.raises(ValidationError, match="ENABLE_LEGACY_API_KEY"):
        Settings(
            app_env="production",
            admin_token="x" * 32,
            enable_legacy_api_key=True,
        )


def test_settings_reject_short_admin_token_outside_local() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(app_env="production", admin_token="too-short")


def test_settings_generates_local_admin_token_when_missing() -> None:
    settings = Settings(app_env="local", admin_token="")

    assert len(settings.admin_token) >= 32


def test_settings_generates_dev_admin_token_when_missing() -> None:
    settings = Settings(app_env="dev", admin_token="")

    assert len(settings.admin_token) >= 32


def test_settings_allow_local_legacy_api_key_for_demo() -> None:
    settings = Settings(
        app_env="local",
        admin_token="local-owner-token",
        enable_legacy_api_key=True,
    )

    assert settings.enable_legacy_api_key is True

from secrets import compare_digest
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_token = HTTPBearer(auto_error=False)


def require_admin_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_token),
    api_key: str | None = Security(_api_key_header),
) -> None:
    settings = get_settings()

    if credentials is not None:
        if (
            credentials.scheme.lower() == "bearer"
            and compare_digest(credentials.credentials, settings.admin_token)
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_admin_token",
                "message": "Invalid admin token.",
            },
        )

    # Deprecated local/demo compatibility path. Hosted deployments should use
    # Authorization: Bearer <ADMIN_TOKEN> and avoid exposing secrets to frontend env.
    if (
        settings.app_env == "local"
        and settings.enable_legacy_api_key
        and api_key
        and compare_digest(
            api_key,
            settings.app_api_key,
        )
    ):
        return

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "missing_admin_token",
                "message": "Missing Authorization bearer token.",
            },
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_admin_token",
            "message": "Invalid admin token.",
        },
    )


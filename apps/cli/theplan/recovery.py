from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from theplan.errors import CliError, exit_code_for_api_status
from theplan.input_helpers import read_secret_stdin

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# apps/api/app/services/auth_users.py:
#   reset_password_for_recovery(db, identifier, *, password=, generate=)


def _load_recovery_fn():
    try:
        from app.services.auth_users import reset_password_for_recovery
    except ImportError as exc:
        raise CliError(
            code="SERVICE_UNAVAILABLE",
            message=(
                "Host-local recovery requires apps/api on PYTHONPATH with API dependencies "
                f"installed ({exc})."
            ),
            exit_code=4,
        ) from exc
    return reset_password_for_recovery


def _resolve_password(
    *,
    generate: bool,
    password: str | None,
    use_stdin: bool,
) -> tuple[str | None, bool]:
    if sum(1 for x in (generate, password is not None, use_stdin) if x) != 1:
        raise CliError(
            code="INVALID_USAGE",
            message="Specify exactly one of --generate, --password, or --password-stdin",
            exit_code=1,
        )
    if generate:
        return None, True
    if use_stdin:
        # Same CRLF trim as login. A leftover \r becomes part of the secret.
        return read_secret_stdin(), False
    assert password is not None
    return password, False


def _map_api_error(exc: Exception) -> CliError:
    from app.api.errors import ApiError

    if isinstance(exc, ApiError):
        detail = exc.content.get("detail", str(exc))
        code = str(exc.content.get("code", "API_ERROR"))
        return CliError(
            code=code,
            message=str(detail),
            exit_code=exit_code_for_api_status(exc.status_code),
        )
    return CliError(
        code="API_ERROR",
        message=str(exc),
        exit_code=4,
    )


def _normalize_result(result: Any) -> tuple[Any, str | None]:
    if isinstance(result, tuple) and len(result) == 2:
        return result[0], result[1]
    if hasattr(result, "user"):
        user = result.user
        temp = getattr(result, "temporary_password", None)
        return user, temp
    return result, None


def _user_payload(user: Any, temporary_password: str | None) -> dict[str, Any]:
    user_id = user.id
    if isinstance(user_id, UUID):
        user_id = str(user_id)
    payload: dict[str, Any] = {
        "user_id": user_id,
        "username": user.username,
        "email": user.email,
        "must_change_password": bool(getattr(user, "must_change_password", True)),
    }
    if temporary_password is not None:
        payload["temporary_password"] = temporary_password
    return payload


def run_reset_password(
    db: Session,
    *,
    user: str,
    generate: bool,
    password: str | None,
    password_stdin: bool,
) -> dict[str, Any]:
    identifier = user.strip()
    if not identifier:
        raise CliError(
            code="INVALID_USAGE",
            message="--user is required",
            exit_code=1,
        )

    new_password, do_generate = _resolve_password(
        generate=generate,
        password=password,
        use_stdin=password_stdin,
    )

    fn = _load_recovery_fn()

    try:
        result = fn(
            db,
            identifier,
            password=new_password if not do_generate else None,
            generate=do_generate,
        )
    except Exception as exc:
        raise _map_api_error(exc) from exc

    user_obj, temp_from_service = _normalize_result(result)
    temporary_password: str | None = temp_from_service if do_generate else None

    return _user_payload(user_obj, temporary_password)

from __future__ import annotations


class CliError(Exception):
    """Structured CLI failure mapped to agent exit codes."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        exit_code: int = 1,
        extra: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.extra = extra
        super().__init__(message)


def exit_code_for_api_status(status_code: int) -> int:
    if status_code == 401 or status_code == 403:
        return 2
    if status_code == 404:
        return 3
    if status_code == 409:
        return 5
    if status_code >= 500:
        return 4
    if status_code == 422:
        return 1
    return 4

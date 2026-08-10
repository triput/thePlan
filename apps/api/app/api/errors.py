from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str, code: str, **extra: object) -> None:
        self.status_code = status_code
        self.content: dict[str, object] = {"detail": detail, "code": code, **extra}


def register_exception_handlers(app) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.content)

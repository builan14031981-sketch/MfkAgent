from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code


async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.code,
        content={"error": exc.message, "code": exc.code},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": exc.status_code},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error["loc"])
        errors.append(f"{loc}: {error['msg']}")
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "code": 422, "details": errors},
    )

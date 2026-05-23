import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from clothist_api.api.router import api_router
from clothist_api.middleware import RequestIDMiddleware
from clothist_api.rate_limit import limiter
from clothist_api.settings import get_settings


def _assert_single_worker() -> None:
    """In-process caches (FX lru_cache, intent TTLCache+singleflight, facets
    dict) assume one uvicorn worker. Make the assumption enforceable so
    accidentally running with `--workers 2` fails fast instead of silently
    breaking cache coherency.
    """
    workers = os.getenv("UVICORN_WORKERS", "1")
    if workers != "1":
        raise RuntimeError(
            f"Clothist MVP requires UVICORN_WORKERS=1 (got {workers}); "
            "in-process caches (TTLCache, facets, FX lru_cache) are per-worker. "
            "Set UVICORN_WORKERS=1 or migrate caches to Redis before going multi-worker."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "rate limit exceeded — try again in 60s",
            "retry_after": 60,
        },
        headers={"Retry-After": "60"},
    )


def create_app() -> FastAPI:
    _assert_single_worker()
    settings = get_settings()
    app = FastAPI(
        title="Clothist API",
        version="0.0.1",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()

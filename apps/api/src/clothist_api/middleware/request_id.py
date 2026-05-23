"""Per-request correlation ID middleware.

Reads `X-Request-ID` from the incoming request, generates a uuid4 if absent,
echoes it on the response, and stashes it on `request.state.request_id` so
route handlers and the structured log line can carry the same id.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(HEADER) or uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[HEADER] = rid
        return response

"""Shared rate-limiter instance.

Single Limiter so both `main.py` (mounting the exception handler) and
`api/search.py` (decorating the /intent route) reference the same object.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

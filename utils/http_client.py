from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

DEFAULT_TIMEOUT = 10.0


@asynccontextmanager
async def get_http_client(timeout: float = DEFAULT_TIMEOUT) -> AsyncIterator[httpx.AsyncClient]:
    """
    Provide a configured HTTPX async client for service integrations.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client

"""
Concurrency limiting middleware for MDS Provider API.
"""

import asyncio
import logging
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ConcurrencyMiddleware(BaseHTTPMiddleware):
    """Middleware to limit concurrent requests to prevent resource exhaustion."""

    def __init__(self, app, max_concurrent_requests: int = 10):
        super().__init__(app)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.max_concurrent = max_concurrent_requests
        logger.info(f"ConcurrencyMiddleware initialized with max_concurrent_requests={max_concurrent_requests}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with concurrency limiting.

        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain

        Returns:
            Response object
        """
        # Skip concurrency limiting for health checks and static endpoints
        if request.url.path in ["/", "/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Check if we can acquire a semaphore slot
        if self.semaphore.locked():
            logger.warning(f"Too many concurrent requests. Max: {self.max_concurrent}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "error_description": f"Too many concurrent requests. Maximum {self.max_concurrent} allowed."
                }
            )

        async with self.semaphore:
            try:
                logger.debug(f"Processing request: {request.method} {request.url.path}")
                response = await call_next(request)
                return response
            except Exception as e:
                logger.error(f"Request failed: {request.method} {request.url.path} - {str(e)}")
                raise
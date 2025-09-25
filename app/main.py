"""
MDS Provider API for Autonomous Delivery Robots

This FastAPI application implements the Mobility Data Specification (MDS) 2.0+
Provider API for autonomous delivery robot services.
"""

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.endpoints import vehicles, trips, events, admin
from app.auth.middleware import AuthMiddleware
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting MDS Provider API...")
    yield
    # Shutdown
    print("Shutting down MDS Provider API...")


app = FastAPI(
    title="MDS Provider API - Delivery Robots",
    description="Mobility Data Specification Provider API for autonomous delivery robot services",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with MDS-compliant error responses."""
    try:
        error_code = exc.detail.get("error_code", "unknown_error") if isinstance(exc.detail, dict) else "unknown_error"
        error_details = str(exc.detail.get("error_details", "Unknown details")) if isinstance(exc.detail, dict) else str(exc.detail)
    except (AttributeError, TypeError):
        error_code = "unknown_error"
        error_details = str(exc.detail) if exc.detail else "Unknown error occurred"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_code,
            "error_description": error_details,
            "error_details": error_details
        },
        headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with proper 400 status code."""
    return JSONResponse(
        status_code=400,
        content={
            "error": "validation_error",
            "error_description": str(exc),
            "error_details": str(exc)
        },
        headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
    )


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time and MDS content-type headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    # Add MDS content-type header if not already set
    if "Content-Type" not in response.headers:
        response.headers["Content-Type"] = f"application/vnd.mds+json;version={settings.MDS_VERSION}"

    return response


# CORS middleware
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],  # MDS Provider API is read-only
    allow_headers=["*"],
)

# Authentication middleware
app.add_middleware(AuthMiddleware)

# Include API routers
app.include_router(
    vehicles.router,
    prefix="/vehicles",
    tags=["Vehicles"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    trips.router,
    prefix="/trips",
    tags=["Trips"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    events.router,
    prefix="/events",
    tags=["Events"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"],
    responses={404: {"description": "Not found"}},
)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information."""
    return {
        "service": "MDS Provider API",
        "mode": "delivery-robots",
        "version": settings.MDS_VERSION,
        "provider_id": settings.PROVIDER_ID,
        "documentation": "/docs"
    }


@app.get("/health", include_in_schema=False)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": int(time.time() * 1000),
        "version": settings.MDS_VERSION
    }
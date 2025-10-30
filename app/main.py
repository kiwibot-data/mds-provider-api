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

from app.endpoints import vehicles, trips, events, admin, telemetry
from app.auth.middleware import AuthMiddleware
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting MDS Provider API...")
    print(f"MDS Version: {settings.MDS_VERSION}")
    print(f"Provider ID: {settings.PROVIDER_ID}")
    print(f"Debug Mode: {settings.DEBUG}")
    
    # Validate configuration
    try:
        from app.auth.jwt_handler import jwt_handler
        print("✅ JWT handler initialized")
    except Exception as e:
        print(f"⚠️  JWT handler initialization warning: {e}")
    
    try:
        from app.auth.api_key_handler import api_key_handler
        print("✅ API key handler initialized")
    except Exception as e:
        print(f"⚠️  API key handler initialization warning: {e}")
    
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
        # Use 'error' as the key to be consistent with tests
        error_code = exc.detail.get("error", "unknown_error") if isinstance(exc.detail, dict) else "unknown_error"
        error_description = str(exc.detail.get("error_description", "Unknown details")) if isinstance(exc.detail, dict) else str(exc.detail)
    except (AttributeError, TypeError):
        error_code = "unknown_error"
        error_description = str(exc.detail) if exc.detail else "Unknown error occurred"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_code,
            "error_description": error_description,
        },
        headers={"Content-Type": f"application/vnd.mds+json;version={settings.MDS_VERSION}"}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with proper 422 status code."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "error_description": str(exc),
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

app.include_router(
    telemetry.router,
    prefix="/telemetry",
    tags=["Telemetry"],
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
        "version": settings.MDS_VERSION,
        "provider_id": settings.PROVIDER_ID,
        "debug_mode": settings.DEBUG
    }


@app.get("/test-auth", include_in_schema=False)
async def test_auth(request: Request):
    """Test authentication endpoint for debugging."""
    try:
        from app.auth.middleware import get_current_provider_id
        provider_id = get_current_provider_id(request)
        auth_type = request.state.auth.get("auth_type", "unknown") if hasattr(request.state, "auth") else "none"
        return {
            "status": "authenticated",
            "provider_id": provider_id,
            "auth_type": auth_type
        }
    except Exception as e:
        return {
            "status": "authentication_failed",
            "error": str(e),
            "debug_mode": settings.DEBUG
        }
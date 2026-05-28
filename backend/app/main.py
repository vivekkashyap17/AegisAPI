from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.api.routes import router
from app.core.db import engine, Base
from app.core.config import settings

# -------------------------------------------------------
# LOGGING SETUP
# -------------------------------------------------------
# Gives you timestamped logs in the console so you can
# see exactly what's happening and when.
# In production you'd write these to a file or log service.
# -------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------
# LIFESPAN MANAGER
# -------------------------------------------------------
# Modern FastAPI way to handle startup and shutdown logic.
# Everything BEFORE yield runs on startup.
# Everything AFTER yield runs on shutdown.
#
# Why lifespan instead of @app.on_event("startup")?
# on_event is deprecated in newer FastAPI versions.
# Lifespan is the current recommended pattern.
# -------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info("Initializing database tables...")

    async with engine.begin() as conn:
        # Creates tables if they don't exist yet
        # Safe to run every startup — won't overwrite existing tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables ready")
    logger.info(f"{settings.APP_NAME} is running")

    yield  # Application runs here

    # --- SHUTDOWN ---
    logger.info("Shutting down — disposing database connections...")
    await engine.dispose()
    logger.info("Shutdown complete")


# -------------------------------------------------------
# FASTAPI APP INSTANCE
# -------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent backend-driven API security platform",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI at /docs
    redoc_url="/redoc",     # ReDoc UI at /redoc
    lifespan=lifespan       # Wire in the lifespan manager
)


# -------------------------------------------------------
# CORS MIDDLEWARE
# -------------------------------------------------------
# CORS = Cross-Origin Resource Sharing
# Browsers block fetch() calls to a different origin by default.
# Your frontend runs on localhost:5500 (or similar),
# your backend runs on localhost:8000 — different ports
# means different origins — browser blocks it without this.
#
# allow_origins: which frontends can talk to this API
# allow_methods: which HTTP methods are allowed
# allow_headers: which headers the frontend can send
#
# In production, replace "*" in origins with your actual
# frontend domain — never use "*" in production.
# -------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Dev only — lock this down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------
# REQUEST TIMING MIDDLEWARE
# -------------------------------------------------------
# Runs on every single request.
# Measures how long each request takes and logs it.
# This is how you catch slow endpoints early.
#
# middleware("http") means it intercepts all HTTP requests
# before they reach any route.
# -------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Pass request to the actual route handler
    response = await call_next(request)

    # Calculate how long it took
    duration = (time.time() - start_time) * 1000  # convert to milliseconds

    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} "
        f"({duration:.2f}ms)"
    )

    # Add timing to response headers — useful for debugging
    response.headers["X-Response-Time"] = f"{duration:.2f}ms"

    return response


# -------------------------------------------------------
# GLOBAL EXCEPTION HANDLER
# -------------------------------------------------------
# Catches any unhandled exception in any route.
# Returns a clean JSON error instead of a raw Python traceback.
# Never expose raw tracebacks to clients — they reveal
# internal implementation details to attackers.
# -------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
            # Never put exc details here in production
        }
    )


# -------------------------------------------------------
# ROUTERS
# -------------------------------------------------------
# Mount your route modules here with a prefix.
# /api/v1 prefix means all your routes become:
# /api/v1/ingest, /api/v1/logs, etc.
# Versioning from day one — when you build v2,
# old clients still work on v1.
# -------------------------------------------------------
app.include_router(router, prefix="/api/v1")


# -------------------------------------------------------
# ROOT ENDPOINTS
# -------------------------------------------------------
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME
    }
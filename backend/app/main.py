from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.api.routes import router
from app.api.auth import router as auth_router
from app.core.db import engine, Base
from app.core.config import settings
from app.core.redis import connect_redis, disconnect_redis
from app.models import user  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info("Initializing database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables ready")
    await connect_redis()
    logger.info("Redis connected")
    logger.info(f"{settings.APP_NAME} is running")

    yield

    logger.info("Shutting down — disposing database connections...")
    await engine.dispose()
    await disconnect_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent backend-driven API security platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Restrict CORS to known frontend origins — a wildcard with credentials is both
# unsafe and rejected by browsers. Add your real frontend origin(s) here.
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} "
        f"({duration:.2f}ms)"
    )
    response.headers["X-Response-Time"] = f"{duration:.2f}ms"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    # Full detail goes to the server logs only — never to the client
    error_detail = traceback.format_exc()
    logger.error(f"Unhandled exception: {exc}")
    logger.error(error_detail)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


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
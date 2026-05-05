from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# The async engine — handles the actual PostgreSQL connection pool
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,        # logs all SQL queries to console — turn off in production
    pool_size=10,     # max persistent connections in the pool
    max_overflow=20   # extra connections allowed under burst load
)

# Session factory — each request gets its own session (isolated transaction)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # keeps objects usable after commit
)

# Base class — all your ORM models (tables) will inherit from this
Base = declarative_base()


# Dependency — FastAPI routes will call this to get a DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session          # hand the session to the route
            await session.commit() # auto-commit if no error
        except Exception:
            await session.rollback() # roll back on any failure
            raise
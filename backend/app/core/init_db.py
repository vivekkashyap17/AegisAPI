import asyncio
from app.core.db import engine, Base

# Import all models here so Base knows about them before creating tables
from app.models.audit import AuditLog


async def init():
    async with engine.begin() as conn:
        # Creates all tables that don't exist yet — safe to run multiple times
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")


if __name__ == "__main__":
    asyncio.run(init())
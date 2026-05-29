import asyncio
from app.core.db import engine, Base
from app.models.audit import AuditLog
from app.models.user import User


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")


if __name__ == "__main__":
    asyncio.run(init())
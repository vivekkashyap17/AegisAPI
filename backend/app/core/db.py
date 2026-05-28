from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# The async engine — handles the actual PostgreSQL connection pool
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,        
    pool_size=10,    
    max_overflow=20  
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session         
            await session.commit() 
        except Exception:
            await session.rollback()
            raise
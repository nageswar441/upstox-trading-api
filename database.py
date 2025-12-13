import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

# Example: postgresql+asyncpg://user:password@localhost/dbname
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback or error if not set. 
    # For now, we can raise an error or warn.
    # raise ValueError("DATABASE_URL is not set in environment variables")
    print("WARNING: DATABASE_URL is not set. Database features will fail.")
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/upstox_db"

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

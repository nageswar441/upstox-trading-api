import asyncio
from database import engine, Base
from auth.models import *  # Import all models to ensure they are registered with Base

async def init_db():
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())

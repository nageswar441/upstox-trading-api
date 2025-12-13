import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# Read from env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env, using defaults/overrides if available, or failing.")
    # Attempt to construct if individual vars exist, or parse DATABASE_URL
    # For this script we need 'postgres' db connection first.

# Parse the target DB name from the URL or env
# Assuming DATABASE_URL is like postgresql+asyncpg://user:pass@host:port/dbname
try:
    # Remove +asyncpg if present for standard parsing if needed, but urlparse handles it mostly
    parsed = urlparse(DATABASE_URL.replace("+asyncpg", ""))
    DB_USER = parsed.username or "postgres"
    DB_PASS = parsed.password or "postgres"
    DB_HOST = parsed.hostname or "localhost"
    DB_PORT = parsed.port or 5432
    TARGET_DB = parsed.path.lstrip("/") or "upstox_db"
except Exception:
    # Fallback to defaults or individual vars
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASS", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    TARGET_DB = os.getenv("DB_NAME", "upstox_db")

async def create_database():
    print(f"Connecting to postgres as {DB_USER} on {DB_HOST}:{DB_PORT}...")
    sys_conn_str = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
    
    try:
        conn = await asyncpg.connect(sys_conn_str)
        # Check if database exists
        exists = await conn.fetchval(f"SELECT 1 FROM pg_database WHERE datname = '{TARGET_DB}'")
        
        if not exists:
            print(f"Database '{TARGET_DB}' does not exist. Creating...")
            await conn.execute(f'CREATE DATABASE "{TARGET_DB}"')
            print(f"Database '{TARGET_DB}' created successfully.")
        else:
            print(f"Database '{TARGET_DB}' already exists.")
            
        await conn.close()
        
    except Exception as e:
        print(f"Error creating database: {e}")

if __name__ == "__main__":
    asyncio.run(create_database())

import os
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import redis.asyncio as redis
from dotenv import load_dotenv
from app.core.config import settings

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL") or settings.DATABASE_URL
REDIS_URL = os.getenv("REDIS_URL") or settings.REDIS_URL

print(f"🔧 Using DATABASE_URL: {DATABASE_URL[:50]}...")
print(f"🔧 Using REDIS_URL: {REDIS_URL[:30]}...")

# Convert to asyncpg format for async engine (the RIGHT way)
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

print(f"🔧 Async URL: {ASYNC_DATABASE_URL[:50]}...")

# SQLAlchemy setup with asyncpg
# Increase pool size for handling concurrent requests
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=20,          # Base connections in the pool
    max_overflow=30,       # Additional connections above pool_size
    pool_timeout=30,       # Seconds to wait for a connection
    pool_recycle=1800,     # Recycle connections after 30 minutes
    pool_pre_ping=True,    # Test connections before use
)
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # CRITICAL FIX: Prevent auto-expiring after commit
)

Base = declarative_base()

# Redis setup
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Dependencies
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_session():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_redis():
    return redis.from_url(REDIS_URL)

# Health check functions  
async def check_db_health():
    try:
        async with SessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            return "connected"
    except Exception as e:
        print(f"Database health check failed: {e}")
        return f"error: {str(e)[:50]}"

async def check_redis_health():
    try:
        await redis_client.ping()
        return "connected"
    except Exception as e:
        print(f"Redis health check failed: {e}")
        return f"error: {str(e)[:50]}"
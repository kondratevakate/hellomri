from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine 
from app.core.config import settings

# Заменить на settings
DATABASE_URL = "postgresql+asyncpg://postgres:1917Atdhfkm@localhost:5432/agent"
engine = create_async_engine(DATABASE_URL)

async_session_maker = async_sessionmaker(engine, expire_on_commit = False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

sync_engine = create_engine(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

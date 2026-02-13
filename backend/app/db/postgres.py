from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.postgres_dsn, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_pg_session():
    async with async_session() as session:
        yield session


async def init_postgres():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_postgres():
    await engine.dispose()

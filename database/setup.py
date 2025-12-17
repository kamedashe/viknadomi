from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Using sqlite+aiosqlite for async support
engine = create_async_engine('sqlite+aiosqlite:///db.sqlite3', echo=True)

async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

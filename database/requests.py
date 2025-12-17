from database.setup import async_session
from database.models import User
from sqlalchemy import select, update

async def add_user(tg_id: int, phone: str, username: str | None = None, full_name: str | None = None):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == tg_id))
        
        if not user:
            session.add(User(
                id=tg_id, 
                phone_number=phone, 
                username=username, 
                full_name=full_name,
                is_approved=False
            ))
            await session.commit()
            return True # New user created
        return False # User already exists

async def get_user(tg_id: int) -> User | None:
    async with async_session() as session:
        return await session.scalar(select(User).where(User.id == tg_id))

async def update_user_status(tg_id: int, is_approved: bool):
    async with async_session() as session:
        await session.execute(update(User).where(User.id == tg_id).values(is_approved=is_approved))
        await session.commit()

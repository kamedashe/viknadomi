from database.setup import async_session
from database.models import User, MediaContent
from sqlalchemy import select, update, delete

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

async def get_all_users():
    async with async_session() as session:
        result = await session.scalars(select(User))
        return result.all()

async def update_user_status(tg_id: int, is_approved: bool):
    async with async_session() as session:
        await session.execute(update(User).where(User.id == tg_id).values(is_approved=is_approved))
        await session.commit()

async def add_media(category_code: str, file_id: str, file_type: str, caption: str | None = None):
    async with async_session() as session:
        session.add(MediaContent(
            category_code=category_code,
            file_id=file_id,
            file_type=file_type,
            caption=caption
        ))
        await session.commit()

async def get_media_by_category(category_code: str):
    async with async_session() as session:
        result = await session.scalars(select(MediaContent).where(MediaContent.category_code == category_code))
        return result.all()

async def delete_media_by_category(category_code: str):
    async with async_session() as session:
        await session.execute(delete(MediaContent).where(MediaContent.category_code == category_code))
        await session.commit()

async def get_media_by_id(media_id: int) -> MediaContent | None:
    async with async_session() as session:
        return await session.scalar(select(MediaContent).where(MediaContent.id == media_id))

async def delete_media_by_id(media_id: int):
    async with async_session() as session:
        await session.execute(delete(MediaContent).where(MediaContent.id == media_id))
        await session.commit()

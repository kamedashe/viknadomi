from sqlalchemy import BigInteger, String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from database.setup import Base

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

class MediaContent(Base):
    __tablename__ = 'media_content'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_code: Mapped[str] = mapped_column(String)
    file_id: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)

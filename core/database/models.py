from sqlalchemy import (
    ForeignKey,
    String,
    BigInteger,
    Integer,
    Boolean,
    DateTime,
)
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from utils.dates import UTC_PLUS_3

engine = create_async_engine(
    url="sqlite+aiosqlite:///db.sqlite3",
    echo=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tid: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)  # внешний ID (напр., телеграм)
    name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    points: Mapped[int] = mapped_column(Integer, default=50)
    level: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(255), default='Default')

    date_add: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now(UTC_PLUS_3))
    count_time: Mapped[str | None] = mapped_column(DateTime, nullable=True)

    # Связи
    targets: Mapped[list["Target"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tid={self.tid} name={self.name!r}>"


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    description: Mapped[str] = mapped_column(String(1500))
    date_add: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now(UTC_PLUS_3))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="targets")

    def __repr__(self) -> str:
        return f"<Target id={self.id} user_id={self.user_id} done={self.is_done}>"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    date_start: Mapped[datetime] = mapped_column(DateTime)
    date_end: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    date_add: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now(UTC_PLUS_3))

    user: Mapped[User] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} date_start={self.date_start} date_end={self.date_end} active={self.is_active}>"



# Инициализация БД (создание таблиц)
async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

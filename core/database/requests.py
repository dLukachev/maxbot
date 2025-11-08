from datetime import datetime, timedelta, timezone, date, time
from typing import Optional, Sequence, Union
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from core.database.models import async_session, User, Target, Session
from sqlalchemy import and_

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
DurationInput = Union[int, float, timedelta]

# ---------- Users ----------
class UserCRUD:
    @staticmethod
    async def create(
        *,
        tid: Optional[int],
        name: Optional[str],
        username: Optional[str],
        points: int = 50,
        level: int = 1,
        count_time: Optional[str | None] = None,
    ) -> User:
        async with async_session() as session:
            user = User(tid=tid, name=name, username=username, points=points, level=level, count_time=count_time)
            session.add(user)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise ValueError(f"Конфликт уникального tid: {e}") from e
            await session.refresh(user)
            return user

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[User]:
        async with async_session() as session:
            res = await session.execute(select(User).where(User.id == user_id))
            return res.scalar_one_or_none()

    @staticmethod
    async def get_by_tid(tid: int) -> Optional[User]:
        async with async_session() as session:
            res = await session.execute(select(User).where(User.tid == tid))
            return res.scalar_one_or_none()

    @staticmethod
    async def list(limit: int = 100, offset: int = 0) -> Sequence[User]:
        async with async_session() as session:
            res = await session.execute(select(User).order_by(User.id).limit(limit).offset(offset))
            return res.scalars().all()

    @staticmethod
    async def update(
        user_id: int,
        *,
        name: Optional[str] = None,
        username: Optional[str] = None,
        points: Optional[int] = None,
        level: Optional[int] = None,
        score: Optional[int] = None,
        state: Optional[str] = None,
        count_time: Optional[str | None] = None,
        tid: Optional[int] = None,
    ) -> Optional[User]:
        values = {}
        if name is not None: values["name"] = name
        if username is not None: values["username"] = username
        if points is not None: values["points"] = points
        if level is not None: values["level"] = level
        if score is not None: values["score"] = score
        if state is not None: values["state"] = state
        if count_time is not None: values["count_time"] = count_time
        if tid is not None: values["tid"] = tid

        async with async_session() as session:
            if values:
                try:
                    await session.execute(update(User).where(User.tid == user_id).values(**values))
                    await session.commit()
                except IntegrityError as e:
                    await session.rollback()
                    raise ValueError(f"Конфликт уникального tid: {e}") from e
            res = await session.execute(select(User).where(User.tid == user_id))
            return res.scalar_one_or_none()

    @staticmethod
    async def delete(user_id: int) -> bool:
        """
        Возвращает True, если пользователь существовал и был удалён.
        """
        async with async_session() as session:
            # Проверка существования
            res = await session.execute(select(User.id).where(User.id == user_id))
            exists = res.scalar_one_or_none()
            if exists is None:
                return False
            # Удаление
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
            return True

    @staticmethod
    async def add_duration(user_id: int, amount: DurationInput) -> Optional["User"]:
        """
        Прибавляет длительность к полю count_time пользователя.
        Храним как DateTime = EPOCH + total_seconds. Если count_time=None — считаем 0.
        amount: timedelta | секунды (int/float).
        """
        # нормализуем вход
        seconds = amount.total_seconds() if isinstance(amount, timedelta) else float(amount)
        if seconds < 0:
            # если дали отрицательное — делегируем на subtract, либо считаем как вычитание
            return await UserCRUD.subtract_duration(user_id, -seconds)

        async with async_session() as session:
            # забираем текущего пользователя
            res = await session.execute(select(User).where(User.tid == user_id))
            user = res.scalar_one_or_none()
            if user is None:
                return None

            # переводим текущее значение в накопленные секунды
            current_dt: Optional[datetime] = user.count_time # type: ignore
            if current_dt is None:
                current_seconds = 0.0
            else:
                # Если current_dt без tzinfo, считаем, что это UTC naive → добавим UTC tzinfo
                if current_dt.tzinfo is None:
                    current_dt = current_dt.replace(tzinfo=timezone.utc)
                current_seconds = (current_dt - EPOCH).total_seconds()

            new_total_seconds = current_seconds + seconds
            new_dt_utc = EPOCH + timedelta(seconds=new_total_seconds)

            # Храним как naive (без tzinfo), т.к. SQLite не поддерживает TZ нормально
            store_dt = new_dt_utc.replace(tzinfo=None)

            await session.execute(
                update(User).where(User.tid == user_id).values(count_time=store_dt)
            )
            await session.commit()

            # вернуть актуального пользователя
            res2 = await session.execute(select(User).where(User.tid == user_id))
            return res2.scalar_one_or_none()

    @staticmethod
    async def subtract_duration(user_id: int, amount: DurationInput) -> Optional["User"]:
        """
        Вычитает длительность из поля count_time. Не даём уйти ниже нуля.
        amount: timedelta | секунды (int/float).
        """
        seconds = amount.total_seconds() if isinstance(amount, timedelta) else float(amount)
        if seconds < 0:
            # отрицательное вычитание = прибавление
            return await UserCRUD.add_duration(user_id, -seconds)

        async with async_session() as session:
            res = await session.execute(select(User).where(User.tid == user_id))
            user = res.scalar_one_or_none()
            if user is None:
                return None

            current_dt: Optional[datetime] = user.count_time # type: ignore
            if current_dt is None:
                current_seconds = 0.0
            else:
                if current_dt.tzinfo is None:
                    current_dt = current_dt.replace(tzinfo=timezone.utc)
                current_seconds = (current_dt - EPOCH).total_seconds()

            new_total_seconds = max(0.0, current_seconds - seconds)
            new_dt_utc = EPOCH + timedelta(seconds=new_total_seconds)
            store_dt = new_dt_utc.replace(tzinfo=None)

            await session.execute(
                update(User).where(User.tid == user_id).values(count_time=store_dt)
            )
            await session.commit()

            res2 = await session.execute(select(User).where(User.tid == user_id))
            return res2.scalar_one_or_none()
    
    @staticmethod
    async def points(user_id: int, points: int):
        """Сколько поинтов начислить юзеру"""
        async with async_session() as session:
            result = await session.execute(select(User).where(
                User.tid == user_id
            ))
            result = result.scalar_one_or_none()
            if not result:
                return None
            try:
                obj = update(User).where(User.tid == user_id).values(points=int(result.points) + int(points))
                await session.execute(obj)
                await session.commit()
                return 1
            except Exception as e:
                return e

# ---------- Targets ----------
class TargetCRUD:
    @staticmethod
    async def create(*, user_id: int, description: str, is_done: bool = False) -> Target:
        async with async_session() as session:
            obj = Target(user_id=user_id, description=description, is_done=is_done)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    @staticmethod
    async def get_by_id(target_id: int) -> Optional[Target]:
        async with async_session() as session:
            res = await session.execute(select(Target).where(Target.id == target_id))
            return res.scalar_one_or_none()

    @staticmethod
    async def list_by_user(user_id: int, limit: int = 100, offset: int = 0) -> Sequence[Target]:
        async with async_session() as session:
            res = await session.execute(
                select(Target).where(Target.user_id == user_id).order_by(Target.id).limit(limit).offset(offset)
            )
            return res.scalars().all()

    @staticmethod
    async def update(
        target_id: int,
        *,
        description: Optional[str] = None,
        is_done: Optional[bool] = None,
    ) -> Optional[Target]:
        values = {}
        if description is not None: values["description"] = description
        if is_done is not None: values["is_done"] = is_done

        async with async_session() as session:
            if values:
                await session.execute(update(Target).where(Target.id == target_id).values(**values))
                await session.commit()
            res = await session.execute(select(Target).where(Target.id == target_id))
            return res.scalar_one_or_none()

    @staticmethod
    async def delete(target_id: int) -> bool:
        async with async_session() as session:
            res = await session.execute(select(Target.id).where(Target.id == target_id))
            exists = res.scalar_one_or_none()
            if exists is None:
                return False
            await session.execute(delete(Target).where(Target.id == target_id))
            await session.commit()
            return True
    
    @staticmethod
    async def get_all_target_today(user_id: int, day: date):
        start_dt = datetime.combine(day, time.min) 
        next_day_dt = start_dt + timedelta(days=1)
        async with async_session() as session:
            res = await session.execute(
                select(Target).where(
                    Target.user_id == user_id,
                    Target.date_add >= start_dt,
                    Target.date_add <= next_day_dt,
                )
            )
            return res.all()


# ---------- Sessions ----------
class SessionCRUD:
    @staticmethod
    async def create(*, user_id: int, date_start: datetime, date_end: datetime, is_active: bool = False) -> Session:
        async with async_session() as session:
            obj = Session(user_id=user_id, date_start=date_start, date_end=date_end, is_active=is_active)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    @staticmethod
    async def get_by_id(session_id: int) -> Optional[Session]:
        async with async_session() as session:
            res = await session.execute(select(Session).where(Session.id == session_id))
            return res.scalar_one_or_none()

    @staticmethod
    async def list_by_user(user_id: int, limit: int = 100, offset: int = 0) -> Sequence[Session]:
        async with async_session() as session:
            res = await session.execute(
                select(Session).where(Session.user_id == user_id).order_by(Session.id).limit(limit).offset(offset)
            )
            return res.scalars().all()

    @staticmethod
    async def update(
        session_id: int,
        *,
        date_start: Optional[datetime] = None,
        date_end: Optional[datetime] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Session]:
        values = {}
        if date_start is not None: values["date_start"] = date_start
        if date_end is not None: values["date_end"] = date_end
        if is_active is not None: values["is_active"] = is_active

        async with async_session() as session:
            if values:
                await session.execute(update(Session).where(Session.id == session_id).values(**values))
                await session.commit()
            res = await session.execute(select(Session).where(Session.id == session_id))
            return res.scalar_one_or_none()

    @staticmethod
    async def delete(session_id: int) -> bool:
        async with async_session() as session:
            res = await session.execute(select(Session.id).where(Session.id == session_id))
            exists = res.scalar_one_or_none()
            if exists is None:
                return False
            await session.execute(delete(Session).where(Session.id == session_id))
            await session.commit()
            return True

    @staticmethod
    async def list_by_user_on_date(user_id: int, day: date) -> Sequence["Session"]:
        """
        Возвращает все сессии пользователя за конкретный календарный день.
        Диапазон: [day 00:00:00, (day+1) 00:00:00), по полю date_start.
        """
        start_of_day = datetime.combine(day, datetime.min.time())
        end_of_day = datetime.combine(day + timedelta(days=1), datetime.min.time())

        async with async_session() as session:
            res = await session.execute(
                select(Session)
                .where(
                    and_(
                        Session.user_id == user_id,
                        Session.date_start >= start_of_day,
                        Session.date_start < end_of_day,
                    )
                )
                .order_by(Session.date_start.asc())
            )
            return res.scalars().all()
        
    @staticmethod
    async def total_active_time_on_date(user_id: int, day: date) -> timedelta:
        """
        Возвращает суммарное активное время за указанный день как timedelta.
        Для каждой сессии берём пересечение с окном дня:
        [start_of_day, end_of_day), и суммируем (end - start).
        """
        start_of_day = datetime.combine(day, time.min)
        end_of_day = datetime.combine(day + timedelta(days=1), time.min)

        async with async_session() as session:
            res = await session.execute(
                select(Session).where(
                    and_(
                        Session.user_id == user_id,
                        Session.date_start < end_of_day,   # началась до конца дня
                        Session.date_end >= start_of_day,  # закончилась после начала дня
                    )
                )
            )
            sessions: Sequence["Session"] = res.scalars().all()

        total = timedelta(0)
        for s in sessions:
            # Границы пересечения строго datetime
            start: datetime = max(s.date_start, start_of_day) # type: ignore
            end: datetime = min(s.date_end, end_of_day) # type: ignore
            if end > start:
                total += (end - start)

        return total
    
    @staticmethod
    async def get_active_session(user_id: int):
        async with async_session() as session:
            res = await session.execute(
                select(Session).where(
                    and_(
                        Session.user_id == user_id,
                        Session.is_active == True
                    )
                )
            )
        return res.scalar_one_or_none()

    @staticmethod
    async def get_all_active_session():
        async with async_session() as session:
            res = await session.execute(
                select(Session).where(
                    (
                        Session.is_active == True
                    )
                )
            )
        return res.scalars().all()
    
    @staticmethod
    async def get_all_active_session_by_user(user_id: int):
        async with async_session() as session:
            res = await session.execute(
                select(Session).where(
                    and_(
                        Session.user_id == user_id,
                        Session.is_active == True
                    )
                )
            )
        return res.scalars().all()
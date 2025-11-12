from datetime import datetime

from utils.dates import UTC_PLUS_3
from core.database.requests import SessionCRUD

async def stop_all_sessions(bot):
    """Функция смотрит все активные сессии в бд и закрывает их."""
    sessions = await SessionCRUD.get_all_active_session()
    now = datetime.now(UTC_PLUS_3).replace(tzinfo=None)
    print("Смотрю активные сессии....")
    for session in sessions:
        print("Нашел сессию!")
        await SessionCRUD.update(session_id=session.id, date_end=now, is_active=False)
        await bot.send_message(chat_id=session.user_id, text="Твоя сессия автоматически завершена и учтена!")



async def stop_one_sessions(bot, user_id):
    session = await SessionCRUD.get_active_session(user_id)
    now = datetime.now(UTC_PLUS_3).replace(tzinfo=None)
    print("Смотрю активные сессии....")
    if not session:
        print(f"На ретерн попал, user_id = {user_id}")
        return
    else:
        elapsed = now - session.date_start
        total_seconds = int(elapsed.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        await SessionCRUD.update(session_id=session.id, date_end=now, is_active=False)
        await bot.send_message(user_id=session.user_id, text=f"Твоя сессия автоматически завершена и учтена! \nДобавлено: `{h:02d}:{m:02d}:{s:02d}`")
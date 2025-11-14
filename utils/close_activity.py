from datetime import datetime

from utils.dates import UTC_PLUS_3
from core.database.requests import SessionCRUD

async def stop_all_sessions(bot):
    sessions = await SessionCRUD.get_all_active_session()
    now = datetime.now(UTC_PLUS_3)
    now = now.replace(tzinfo=None)
    print("Смотрю активные сессии....")
    for session in sessions:
        print("Нашел сессию!")
        await SessionCRUD.update(session_id=session.id, date_end=now, is_active=False)
        await bot.send_message(chat_id=session.user_id, text="Твоя сессия автоматически завершена и учтена!")
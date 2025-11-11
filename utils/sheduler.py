from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from redis.commands.search.reducers import count

from core.database.requests import UserCRUD
from utils.dates import UTC_PLUS_3
from core.user_handlers.kb import wright_target

def setup_midnight_messages(bot):
    """
    Настраивает асинхронную отправку сообщений всем пользователям в 12 ночи
    """
    
    async def send_midnight_messages():
        """Асинхронная функция для отправки сообщений всем пользователям"""
        try:
            print(f"🚀 Запуск ночной рассылки в {datetime.now(UTC_PLUS_3)}")
            
            # Асинхронно получаем список пользователей
            users = list(await UserCRUD.list())

            while len(users) == 100:
                users = list(await UserCRUD.list(offset=101))
                message = "Вот и закончился день, начался новый, пора ставить цели!"
                sent_count = 0
                for user in users:
                    try:
                        # Асинхронная отправка сообщения
                        await bot.send_message(user_id=user.tid, text=message, attachments=[wright_target])
                        sent_count += 1
                    except Exception as e:
                        print(f"❌ Ошибка отправки пользователю {user.tid}: {e}")
            
                print(f"✅ Рассылка завершена. Успешно отправлено: {sent_count}/{len(users)}")
            
        except Exception as e:
            print(f"❌ Критическая ошибка в рассылке: {e}")
    
    # Создаем асинхронный планировщик
    scheduler = AsyncIOScheduler()
    
    # Добавляем асинхронную задачу (каждый день в 00:00)
    scheduler.add_job(
        send_midnight_messages,
        trigger=CronTrigger(hour=00, minute=00),
        id='midnight_messages'
    )
    
    # Запускаем планировщик
    scheduler.start()
    
    print("⏰ Асинхронная рассылка в 00:00 настроена!")
    return scheduler

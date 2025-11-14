from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from core.database.requests import UserCRUD
from utils.dates import UTC_PLUS_3
from utils.close_activity import stop_one_sessions
from core.user_handlers.kb import checking_done_target_kb

from utils.guards import CACHE_


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
            next_users = 101
            while len(users) > 0:
                sent_count = 0
                for user in users:
                    try:
                        CACHE_.pop(user.tid)
                        try:
                            await stop_one_sessions(bot, user.tid)
                        except Exception as e:
                            print(f"stop_one_sessions ERROR {e}")
                        try:
                            await bot.send_message(
                                user_id=user.tid,
                                text="Вот и закончился день, начался новый, пора отмечать что сделал, а что нет!",
                                attachments=[checking_done_target_kb],
                            )
                        except Exception as e:
                            print(f"checking_done_target_kb ERROR {e}")
                        sent_count += 1
                    except Exception as e:
                        print(f"❌ Ошибка отправки пользователю {user.tid}: {e}")
                if len(users) == 100:
                    users = list(await UserCRUD.list(offset=next_users))
                    next_users += 100
                    print(
                        f"✅ Рассылка завершена. Успешно отправлено: {sent_count}/{len(users)}"
                    )
                else:
                    print(
                        f"✅ Рассылка завершена. Успешно отправлено: {sent_count}/{len(users)}"
                    )
                    break

        except Exception as e:
            print(f"❌ Критическая ошибка в рассылке: {e}")

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        send_midnight_messages,
        trigger=CronTrigger(hour=16, minute=53),
        id="midnight_messages",
    )

    scheduler.start()

    print("⏰ Асинхронная рассылка в 00:00 настроена!")
    return scheduler

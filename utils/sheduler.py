from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from core.database.requests import UserCRUD
from utils.dates import UTC_PLUS_3
from core.user_handlers.kb import wright_target


def setup_midnight_messages(bot):
    async def send_midnight_messages():
        try:
            print(f"🚀 Запуск ночной рассылки в {datetime.now(UTC_PLUS_3)}")

            users = await UserCRUD.list()

            message = "Вот и закончился день, начался новый, пора ставить цели!"

            sent_count = 0
            for user in users:
                try:
                    await bot.send_message(
                        user_id=user.tid, text=message, attachments=[wright_target]
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"❌ Ошибка отправки пользователю {user.tid}: {e}")

            print(
                f"✅ Рассылка завершена. Успешно отправлено: {sent_count}/{len(users)}"
            )

        except Exception as e:
            print(f"❌ Критическая ошибка в рассылке: {e}")

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        send_midnight_messages,
        trigger=CronTrigger(hour=00, minute=00),
        id="midnight_messages",
    )

    scheduler.start()

    print("⏰ Асинхронная рассылка в 00:00 настроена!")
    return scheduler

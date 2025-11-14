import os
import asyncio
import logging

from core.user_handlers.user import user
from core.user_handlers.finally_ import user_finally
from core.database.models import async_main
from utils.sheduler import setup_midnight_messages

from maxapi import Bot, Dispatcher
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

token = os.getenv("TOKEN", "NOT_FIND_TOKEN")
bot = Bot(token)
dp = Dispatcher()


async def main():
    scheduler = setup_midnight_messages(bot)
    await dp.start_polling(bot)


async def init():
    await async_main()


if __name__ == "__main__":
    dp.include_routers(user_finally, user)
    asyncio.run(init())
    asyncio.run(main())

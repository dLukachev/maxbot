import os
import asyncio
import logging

from core.user_handlers.user import user
from core.database.models import async_main

from maxapi import Bot, Dispatcher
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)

token = os.getenv("TOKEN", "NOT_FIND_TOKEN")
bot = Bot(token)
dp = Dispatcher()

async def main():
    await dp.start_polling(bot)

async def init():
    await async_main()

if __name__ == '__main__':
    dp.include_routers(user)
    asyncio.run(init())
    asyncio.run(main())
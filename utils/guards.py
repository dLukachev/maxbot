import functools
from typing import Callable, Awaitable, Any
from datetime import datetime

from core.database.requests import TargetCRUD
from utils.message_utils import update_menu
from utils.states import UserStates
from core.user_handlers.kb import stop_kb

CACHE_ = dict()

def look_if_not_target(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            event = args[0] if args else None
            user_id = event.from_user.user_id if event else "unknown"

            context = kwargs['context'] if args else None
            user_state = await context.get_state()

            print(user_state)

            if str(user_state) == "UserStates:counted_time" and event.callback.payload != "stop_session":
                print(f"RETURN ---> state = {user_state}")
                await update_menu(context, event.message, text="Сначала заверши подсчет времени!",
                                  attachments=[stop_kb])  # type: ignore
                return None

            if CACHE_.get(user_id, False):
                result = await func(*args, **kwargs)
                return result

            targets = await TargetCRUD.get_all_target_today(user_id, datetime.today())

            if targets:
                result = await func(*args, **kwargs)
                return result
            else:
                await context.set_state(UserStates.new_day)
                CACHE_[user_id] = True

        except Exception as e:
            raise e # Пробрасываем исключение дальше
    return wrapper
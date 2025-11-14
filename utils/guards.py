import functools
from typing import Callable, Awaitable, Any
from datetime import datetime

from maxapi.types import MessageCreated

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
            mc = False
            if event is MessageCreated:
                mc = True
            user_id = event.from_user.user_id if event else "unknown"

            context = kwargs['context'] if args else None
            user_state = await context.get_state()

            if str(user_state) == "UserStates:counted_time" and event.callback.payload != "stop_session" if not mc else event.message.payload != "stop_session":
                print(f"RETURN ---> state = {user_state}")
                await update_menu(context, event.message, text="Сначала заверши подсчет времени!",
                                  attachments=[stop_kb])  # type: ignore
                return None

            if CACHE_.get(user_id, False):
                print(f"NOT IN CACHE state = {user_state}")
                result = await func(*args, **kwargs)
                return result

            user, targets = await TargetCRUD.get_all_target_today(user_id, datetime.today())

            print(f"User - {user}")
            if user is None:
                result = await func(*args, **kwargs)
                return result

            print(f"Targets - {targets}")
            if targets:
                print(f"Do it func")
                result = await func(*args, **kwargs)
                return result
            else:
                print(f"Get state UserStates.new_day")
                await context.set_state(UserStates.new_day)
                CACHE_[user_id] = True

        except Exception as e:
            raise e # Пробрасываем исключение дальше
    return wrapper
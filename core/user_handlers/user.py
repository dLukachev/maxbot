from datetime import datetime
from maxapi import Router, F
from maxapi.types import (
    MessageCreated,
    MessageCallback,
    Command,
    DialogCleared,
    BotStarted,
)
from maxapi.context import MemoryContext
from sqlalchemy import Sequence
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # вывод в консоль
    ],
)

from utils.states import FirstStates, UserStates
from core.user_handlers.kb import (
    wright_target,
    confirmation,
    start_kb,
    stop_kb,
    change_target,
    inline_keyboard_from_items,
    inline_keyboard_from_items_with_checks,
    cancel_button_kb,
    change_time_activity_kb,
    Item,
    inline_keyboard_from_items_for_delete,
)

from utils.random_text import get_text
from utils.message_utils import update_menu
from core.database.requests import UserCRUD, TargetCRUD, SessionCRUD
from utils.redis import get_redis_async, get_state_r, set_state_r, delete_state_r
from utils.dates import UTC_PLUS_3, format_total_duration
from utils.cfg_points import get_levels_config
from utils.dates import hhmmss_to_seconds

user = Router()
redis = get_redis_async()


@user.dialog_cleared()
async def handle_dialog_cleared(event: DialogCleared):
    await event.bot.send_message(chat_id=event.chat_id, user_id=event.user.user_id, text="Меню:", attachments=[start_kb])  # type: ignore


@user.bot_started()
async def handle_bot_starterd(event: BotStarted):
    await event.bot.send_message(chat_id=event.chat_id, user_id=event.user.user_id, text="Меню:", attachments=[start_kb])  # type: ignore


@user.message_created(Command("start"))
async def send_info(message: MessageCreated, context: MemoryContext):
    checking = await UserCRUD.get_by_tid(
        message.from_user.user_id
    )  # pyright: ignore[reportOptionalMemberAccess]

    if not checking:
        await UserCRUD.create(
            tid=message.from_user.user_id,
            name=message.from_user.first_name,
            username=message.from_user.username,
        )  # pyright: ignore[reportOptionalMemberAccess]
        first_name = getattr(message.from_user, "first_name", "")
        text = (
            f"Привет, {first_name}! Ты попал куда надо.\n"
            "Смысл этого бота в том, чтобы помочь тебе не забывать кратковременные цели и отслеживать их выполнение, а так же напоминать об отдыхе)"
        )
        prompt = "А пока напиши свою цель(и):"
        await update_menu(
            context,
            message.message,
            text=f"{text}\n\n{prompt}",
            attachments=[wright_target],
        )
        await context.set_state(FirstStates.wait_on_click_on_first_button)
    else:
        await update_menu(
            context, message.message, text="Главное меню:", attachments=[start_kb]
        )


@user.message_created(F.text, FirstStates.wait_on_click_on_first_button)
async def blocker(message: MessageCreated):
    """Блокируем любые текстовые сообщения на момент FirstStates.wait_on_click_on_first_button,
    потом это нигде не используется
    """
    pass


@user.message_callback(F.callback.payload.in_({"back_wright_target", "not_right"}))
async def wrt_in_db(callback: MessageCallback, context: MemoryContext):
    current = await context.get_state()
    text = get_text("instructions_for_wrighting")

    if text and callback.callback.payload == "back_wright_target":
        try:
            await callback.message.edit(text=text)  # type: ignore
        except Exception:
            await update_menu(context, callback.message, text)  # type: ignore
    elif callback.callback.payload == "back_change_target":
        try:
            await callback.message.edit(text=get_text("instructions_for_wrighting"))  # type: ignore
        except Exception:
            await update_menu(context, callback.message, get_text("instructions_for_wrighting"))  # type: ignore

    await context.set_state(UserStates.wrighting_targets)


@user.message_created(UserStates.wrighting_targets)
async def get_and_wright_targets_in_db(message: MessageCreated, context: MemoryContext):
    texts = message.message.body.text  # type: ignore
    mid = await context.get_data()
    mid = mid.get("mid")
    answer = ""
    index = 1
    if texts is not None:
        texts = texts.replace(", ", ",").split(",")
        for text in texts:
            answer += f"{index}. {text}\n"
            index += 1

    print("ПОПАЛ СЮДА -------------")
    result = await message.message.answer(
        f"Твой список:\n{answer}\nВерно?", attachments=[confirmation]
    )
    print(f"{result} результат <---------")
    await context.set_data({"targets": texts})


@user.message_callback(F.callback.payload == "right", UserStates.wrighting_targets)
async def get_and_wright_targets_in_db_R(
    callback: MessageCallback, context: MemoryContext
):
    data = await context.get_data()
    targets = data.get("targets")
    if not targets:
        await update_menu(context, callback.message, text="Какая то ошибка, попробуй снова:(", attachments=[start_kb])  # type: ignore
        return
    for target in targets:
        await TargetCRUD.create(user_id=callback.from_user.user_id, description=target)  # type: ignore

    await update_menu(context, callback.message, text="Успешно!", attachments=[start_kb])  # type: ignore
    await context.clear()


@user.message_callback(F.callback.payload == "back_change_target")
async def change_targets(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        try:
            await callback.message.edit(text="Сначала заверши подсчет времени!", attachments=[stop_kb])  # type: ignore
        except Exception:
            await update_menu(context, callback.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])  # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today())  # type: ignore
    if items == []:
        return
    try:
        await callback.message.edit(text="Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")])  # type: ignore
    await context.set_data({"items": items})


@user.message_callback(F.callback.payload == "target_is_done")
async def make_target_is_done(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, callback.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])  # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today())  # type: ignore
    if items == []:
        return
    initial_checked = set()
    for group in items:
        for t in group:
            if getattr(t, "is_done", False):
                initial_checked.add(t.id)
    await context.set_data({"items": items, "pending_done": list(initial_checked)})
    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description))
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items_with_checks(model_groups, initial_checked, "done")])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items_with_checks(model_groups, initial_checked, "done")])  # type: ignore


@user.message_callback(F.callback.payload == "cancel_change_target")
async def cancel_change_targets(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, callback.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])  # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    data = await context.get_data()
    if not data:
        data = await TargetCRUD.get_all_target_today(user_id=callback.from_user.user_id, day=datetime.today())  # type: ignore

    answer = ""
    ind = 1
    if isinstance(data, list):
        for i in data:
            for j in i:
                mark = "✅" if getattr(j, "is_done", False) else "❌"
                answer += f"{ind}. {mark} {j.description}\n"
                ind += 1
    else:
        for a in data.get("items", []):  # pyright: ignore[reportAttributeAccessIssue]
            for index, item in enumerate(a):
                mark = "✅" if getattr(item, "is_done", False) else "❌"
                answer += f"{ind}. {mark} {item.description}\n"
                ind += 1
    await context.clear()
    try:
        await callback.message.edit(text=f"Твои цели на сегодня:\n{answer}", attachments=[change_target])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text=f"Твои цели на сегодня:\n{answer}", attachments=[change_target])  # type: ignore


@user.message_callback(F.callback.payload == "back_to_menu")
async def back_to_menu(callback: MessageCallback, context: MemoryContext):
    """Generic cancel handler: return to main menu and clear ephemeral context."""
    await context.clear()
    try:
        await callback.message.edit(text="Главное меню:", attachments=[start_kb])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Главное меню:", attachments=[start_kb])  # type: ignore


@user.message_callback(F.callback.payload.startswith("item:"))
async def take_id_and_change(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, callback.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])  # type: ignore
        return
    id = callback.callback.payload
    if not id:
        await update_menu(context, callback.message, text="Ошибка! Хз почему, но айди не вижу(")  # type: ignore
        return
    id = id.split(":")[1]
    await context.set_data({"target_id": id})
    try:
        await callback.message.edit(text="Напиши цель снова и я ее изменю (тут можно запятые кста)")  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Напиши цель снова и я ее изменю (тут можно запятые кста)")  # type: ignore
    await context.set_state(UserStates.change_targets)


@user.message_callback(F.callback.payload == "back_add_target")
async def add_target(callback: MessageCallback, context: MemoryContext):
    await context.set_state(UserStates.wrighting_targets)
    try:
        sended_message = await callback.message.edit(
            text=f"Введите дополнительные цели", attachments=[cancel_button_kb]
        )
    except Exception:
        await update_menu(
            context,
            callback.message,
            text=f"Введите дополнительные цели",
            attachments=[cancel_button_kb],
        )


@user.message_callback(F.callback.payload == "back_delete_target")
async def delete_target(callback: MessageCallback, context: MemoryContext):
    items = await TargetCRUD.get_all_target_today(user_id=callback.from_user.user_id, day=datetime.today())  # type: ignore
    if not items:
        await update_menu(context, callback.message, text="Нет задач для удаления.")
        return

    await context.set_data({"items": items, "pending_delete": []})

    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(
                Item(
                    id=t.id,
                    description=t.description,
                    is_done=getattr(t, "is_done", False),
                )
            )
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, set(), "delete")])  # type: ignore
    except Exception:
        try:
            await callback.message.edit(text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, set(), "delete")])  # type: ignore
        except Exception:
            await update_menu(context, callback.message, text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, set(), "delete")])  # type: ignore


@user.message_callback(F.callback.payload.startswith("delete:"))
async def delete_target_callback(callback: MessageCallback, context: MemoryContext):
    payload = callback.callback.payload
    if not payload:
        await update_menu(context, callback.message, text="Не вижу такой задачи:(")
        return
    target_id = int(payload.split(":")[1])

    data = await context.get_data() or {}
    items = data.get("items")
    if not items:
        items = await TargetCRUD.get_all_target_today(user_id=callback.from_user.user_id, day=datetime.today())  # type: ignore

    pending = set(data.get("pending_delete", []))
    if target_id in pending:
        pending.remove(target_id)
    else:
        pending.add(target_id)

    await context.set_data({"items": items, "pending_delete": list(pending)})

    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(
                Item(
                    id=t.id,
                    description=t.description,
                    is_done=getattr(t, "is_done", False),
                )
            )
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, pending, "delete")])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, pending, "delete")])  # type: ignore


@user.message_callback(F.callback.payload == "commit_delete")
async def commit_delete_handler(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data() or {}
    pending = list(data.get("pending_delete", []))
    items = data.get("items", [])
    if not pending:
        await update_menu(context, callback.message, text="Нечего удалять.")
        await context.clear()
        return

    deleted = await TargetCRUD.bulk_delete(pending)  # type: ignore
    try:
        await callback.message.edit(text=f"Удалено задач: {deleted}", attachments=[start_kb])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text=f"Удалено задач: {deleted}", attachments=[start_kb])  # type: ignore
    await context.clear()


@user.message_callback(F.callback.payload == "cancel_delete")
async def cancel_delete_handler(callback: MessageCallback, context: MemoryContext):
    await context.clear()
    try:
        await callback.message.edit(text="Отмена удаления.", attachments=[start_kb])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Отмена удаления.", attachments=[start_kb])  # type: ignore


@user.message_callback(F.callback.payload.startswith("done:"))
async def take_id_and_change_isdone(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, callback.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])  # type: ignore
        return

    payload = callback.callback.payload
    if not payload:
        await update_menu(context, callback.message, text="Ошибка! Хз почему, но айди не вижу(")  # type: ignore
        return
    target_id = int(payload.split(":")[1])

    data = await context.get_data() or {}
    items = data.get("items")
    if not items:
        items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today())  # type: ignore
        await context.set_data({"items": items})

    pending = set(data.get("pending_done", []))
    if target_id in pending:
        pending.remove(target_id)
    else:
        pending.add(target_id)

    await context.set_data({"items": items, "pending_done": list(pending)})

    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description))
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items_with_checks(model_groups, pending, "done")])  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items_with_checks(model_groups, pending, "done")])  # type: ignore


@user.message_created(UserStates.change_targets)
async def change_target_in_db(message: MessageCreated, context: MemoryContext):
    msg = message.message.body.text
    if not msg:
        await update_menu(context, message.message, text="Ошибка! Хз почему, но сообщение не увидел(")  # type: ignore
        await context.clear()
        return
    id = await context.get_data()
    id = id.get("target_id", "")
    if id == "":
        await update_menu(context, message.message, text="Ошибка! Хз почему, но айди таски не увидел(")  # type: ignore
        await context.clear()
        return

    await TargetCRUD.update(target_id=id, description=msg)
    await message.message.answer("Готово!")
    items = await TargetCRUD.get_all_target_today(message.from_user.user_id, datetime.today())  # type: ignore
    if items == []:
        print("На ретерн попали")
        return
    await message.message.answer("Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")])  # type: ignore
    await context.set_data({"items": items})


@user.message_callback(F.callback.payload == "commit_done")
async def commit_done_handler(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data() or {}
    pending = set(data.get("pending_done", []))
    items = data.get("items", [])
    if not items:
        await update_menu(context, callback.message, text="Нет задач для подтверждения.")  # type: ignore
        await context.clear()
        return
    applied = 0
    for group in items:
        for t in group:
            if t.id in pending and not t.is_done:
                await TargetCRUD.update(target_id=t.id, is_done=True)  # type: ignore
                applied += 1

    desired = pending
    applied = 0
    removed = 0
    for group in items:
        for t in group:
            if t.id in desired and not t.is_done:
                await TargetCRUD.update(target_id=t.id, is_done=True)  # type: ignore
                applied += 1
            if t.id not in desired and t.is_done:
                await TargetCRUD.update(target_id=t.id, is_done=False)  # type: ignore
                removed += 1

    msg_parts = []
    if applied:
        msg_parts.append(f"Отмечено выполненным: {applied}")
    if removed:
        msg_parts.append(f"Снято отметок: {removed}")
    if not msg_parts:
        msg = "Нет изменений."
    else:
        msg = "; ".join(msg_parts)

    await update_menu(context, callback.message, text=msg, attachments=[start_kb])  # type: ignore
    await context.clear()


@user.message_callback(F.callback.payload == "cancel_done")
async def cancel_done_handler(callback: MessageCallback, context: MemoryContext):
    await context.clear()
    await update_menu(context, callback.message, text="Отменено.", attachments=[start_kb])  # type: ignore


@user.message_callback(F.callback.payload == "start_session")
async def start_going(message: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":  # type: ignore
        await update_menu(
            context,
            message.message,
            text="У тебя уже открыта сессия...",
            attachments=[stop_kb],
        )
        await context.set_state(UserStates.counted_time)
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id)  # type: ignore
        if not session:
            now = datetime.now(UTC_PLUS_3)
            await SessionCRUD.create(user_id=message.from_user.user_id, date_start=now, date_end=now, is_active=True)  # type: ignore
            await context.set_state(UserStates.counted_time)
            await update_menu(
                context,
                message.message,
                text=f"Фиксирую старт... {now.strftime('%m-%d %H:%M:%S')}",
                attachments=[stop_kb],
            )


@user.message_callback(F.callback.payload == "stop_session", UserStates.counted_time)
async def stop_going(message: MessageCallback, context: MemoryContext):
    await context.clear()

    now = datetime.now(UTC_PLUS_3)
    now = now.replace(tzinfo=None)

    session = await SessionCRUD.get_active_session(message.from_user.user_id)  # type: ignore
    if not session:
        await update_menu(
            context,
            message.message,
            text="Ошибка! Не вижу сессии%()",
            attachments=[start_kb],
        )

    await SessionCRUD.update(session_id=session.id, date_end=now, is_active=False)  # type: ignore

    elapsed = now - session.date_start  # type: ignore
    await UserCRUD.add_duration(message.from_user.user_id, elapsed)  # type: ignore

    # красиво выводим
    total_seconds = int(elapsed.total_seconds())
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    await update_menu(
        context,
        message.message,
        text=f"Добавлено: `{h:02d}:{m:02d}:{s:02d}`",
        attachments=[start_kb],
    )


@user.message_callback(F.callback.payload == "get_profile")
async def get_profile(message: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(
            context,
            message.message,
            text="Сначала заверши подсчет времени!",
            attachments=[stop_kb],
        )
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id)  # type: ignore
        if session:
            await context.set_state(UserStates.counted_time)
            await update_menu(
                context,
                message.message,
                text="Сначала заверши подсчет времени!",
                attachments=[stop_kb],
            )
            return

    user_data = await UserCRUD.get_by_tid(message.from_user.user_id)  # type: ignore
    next_level = None
    lp = get_levels_config()
    for i in sorted(lp.keys(), key=int):
        if int(user_data.points) < int(i):  # type: ignore
            next_level = int(i)
            break

    answer = f"{user_data.name}, {user_data.level} уровень.\n"  # type: ignore
    if next_level is not None:
        answer += f"Поинтов: {user_data.points}, до следующего уровня {next_level - int(user_data.points)}\n"  # type: ignore
    else:
        answer += f"Поинтов: {user_data.points} (максимальный уровень достигнут!)\n"  # type: ignore
    answer += f"Общее время активности: {format_total_duration(user_data.count_time)}"  # type: ignore

    await update_menu(
        context, message.message, text=answer, attachments=[change_time_activity_kb]
    )


@user.message_callback(F.callback.payload == "change_time")
async def change_sum_time(callback: MessageCallback, context: MemoryContext):
    prompt = (
        "Напиши время, которое нужно прибавить в формате чч:мм:сс\n\n"
        "Если хочешь убавить, то в формате чч:мм:-сс, важно, чтобы '-' был приписан к ненулевому числу, чтобы вычесть ровно минуту, нужно написать 00:-01:00"
    )
    try:
        await callback.message.edit(text=prompt)  # type: ignore
    except Exception:
        await update_menu(context, callback.message, text=prompt)  # type: ignore
    await context.set_state(UserStates.take_time)


@user.message_created(UserStates.take_time)
async def get_time(message: MessageCreated, context: MemoryContext):

    text = message.message.body.text
    time = hhmmss_to_seconds(text)  # type: ignore
    if time is None:
        await update_menu(
            context,
            message.message,
            text="Какая то ошибка.. Попробуй снова",
            attachments=[change_time_activity_kb],
        )
        return
    res = await UserCRUD.add_duration(message.from_user.user_id, time)  # type: ignore
    if res is None:
        await update_menu(
            context,
            message.message,
            text="Какая то ошибка.. Попробуй снова",
            attachments=[change_time_activity_kb],
        )
        return

    user_data = await UserCRUD.get_by_tid(message.from_user.user_id)  # type: ignore
    next_level = None
    lp = get_levels_config()
    for i in sorted(lp.keys(), key=int):
        if int(user_data.points) < int(i):  # type: ignore
            next_level = int(i)
            break

    answer = f"{user_data.name}, {user_data.level} уровень.\n"  # type: ignore
    if next_level is not None:
        answer += f"Поинтов: {user_data.points}, до следующего уровня {next_level - int(user_data.points)}\n"  # type: ignore
    else:
        answer += f"Поинтов: {user_data.points} (максимальный уровень достигнут!)\n"  # type: ignore
    answer += f"Общее время активности: {format_total_duration(user_data.count_time)}"  # type: ignore
    try:
        await update_menu(
            context,
            message.message,
            text=f"Успешно!\n\n{answer}",
            attachments=[change_time_activity_kb],
        )
    except Exception:
        await update_menu(context, message.message, text=f"Успешно!\n\n{answer}")

    await context.clear()


@user.message_callback(F.callback.payload == "get_targets")
async def get_targets(message: MessageCreated, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(
            context,
            message.message,
            text="Сначала заверши подсчет времени!",
            attachments=[stop_kb],
        )
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id)  # type: ignore
        if session:
            await context.set_state(UserStates.counted_time)
            await update_menu(
                context,
                message.message,
                text="Сначала заверши подсчет времени!",
                attachments=[stop_kb],
            )
            return

    target = await TargetCRUD.get_all_target_today(message.from_user.user_id, datetime.today())  # type: ignore
    if target == []:
        await update_menu(
            context,
            message.message,
            text="Почему то не вижу твоих целей на сегодня(\nВозможно ты их просто не написал(а)..(в общем где-то моя ошибка)\n\nНапиши их прямо сейчас, ловлю!",
        )
        await context.set_state(UserStates.wrighting_targets)
        return
    answer = ""
    ind = 1
    for a in target:
        for index, item in enumerate(a):
            mark = "✅" if getattr(item, "is_done", False) else "❌"
            answer += f"{ind}. {mark} {item.description}\n"
            ind += 1
    await update_menu(
        context,
        message.message,
        text=f"Твои цели на сегодня:\n{answer}",
        attachments=[change_target],
    )
    await context.set_data({"items": target})

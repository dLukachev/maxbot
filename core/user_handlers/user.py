from datetime import datetime, timedelta
from maxapi import Router, F
from maxapi.types import MessageCreated, MessageCallback, Command, DialogCleared, BotStarted
from maxapi.context import MemoryContext
from sqlalchemy import Sequence
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # вывод в консоль
    ]
)

from utils.states import UserStates
from core.user_handlers.kb import (
    button_in_help,
    confirmation,
    start_kb,
    stop_kb,
    change_target,
    inline_keyboard_from_items,
    inline_keyboard_from_items_with_checks,
    cancel_button_kb,
    change_time_activity_kb,
    back_to_profile_kb,
    create_profile_targets_keyboard,
    Item,
    inline_keyboard_from_items_for_delete,
    confirmation_finally,
    create_new_target_kb
)

from utils.random_text import get_text
from utils.message_utils import update_menu
from core.database.requests import UserCRUD, TargetCRUD, SessionCRUD
from utils.redis import get_redis_async
from utils.dates import UTC_PLUS_3, format_total_duration
from utils.cfg_points import get_levels_config
from utils.dates import hhmmss_to_seconds, format_duration
from utils.guards import look_if_not_target

user = Router()
redis = get_redis_async()

@user.message_callback(UserStates.new_day)
async def blocker(callback: MessageCallback, context: MemoryContext):
    """Блокируем взаимодействие с ботом, пока не войдет в
    состояние написания новых целей, тогда и будет апдейт стейта"""
    await callback.message.answer(text="Тебе сначало нужно поставить цели!", attachments=[create_new_target_kb])
    pass

@user.dialog_cleared()
@look_if_not_target
async def handle_dialog_cleared(event: DialogCleared, context: MemoryContext):
    check = await UserCRUD.get_by_tid(event.from_user.user_id)
    if not check:
        await UserCRUD.create(tid=event.from_user.user_id, name=event.from_user.first_name, chat_id=event.chat_id, username=event.from_user.username)
    await event.bot.send_message(chat_id=event.chat_id, user_id=event.user.user_id, text="Меню:", attachments=[start_kb]) # type: ignore

@user.bot_started()
async def handle_bot_started(event: BotStarted):
    check = await UserCRUD.get_by_tid(event.from_user.user_id)
    if not check:
        await UserCRUD.create(tid=event.from_user.user_id, chat_id=event.chat_id, name=event.from_user.first_name, username=event.from_user.username)
    await event.bot.send_message(chat_id=event.chat_id, user_id=event.user.user_id, text="Меню:", attachments=[start_kb]) # type: ignore

# ----------------- COMMANDS -----------------

@user.message_created(Command("help"))
async def help(message: MessageCreated, context: MemoryContext):
    #await update_menu(context, message.message, text="привет")
    await message.message.answer("help text", attachments=[button_in_help])


@user.message_callback(F.callback.payload.in_({"back_wright_target", "not_right"}))
@look_if_not_target
async def wrt_in_db(callback: MessageCallback, context: MemoryContext):
    current = await context.get_state()
    text = get_text("instructions_for_wrighting")
    if text and callback.callback.payload == "back_wright_target":
        try:
            await callback.message.edit(text=text) # type: ignore
        except Exception:
            await update_menu(context, callback.message, text) # type: ignore
    elif callback.callback.payload == "back_change_target":
        try:
            await callback.message.edit(text=get_text("instructions_for_wrighting")) # type: ignore
        except Exception:
            await update_menu(context, callback.message, get_text("instructions_for_wrighting")) # type: ignore
    
    await context.set_state(UserStates.wrighting_targets)

@user.message_created(UserStates.wrighting_targets)
@look_if_not_target
async def get_and_wright_targets_in_db(message: MessageCreated, context: MemoryContext):
    texts = message.message.body.text # type: ignore
    fin = await context.get_data()
    is_finally = fin.get("finally")
    answer = ""
    index = 1
    if texts is not None:
        texts = texts.replace(", ", ",").split(",")
        for text in texts:
            answer += f"{index}. {text}\n"
            index += 1

    result = await message.message.answer(f"Твой список:\n{answer}\nВерно?", attachments=[confirmation if not is_finally else confirmation_finally])
    await context.set_data({"targets": texts}) if not is_finally else await context.set_data({"targets": texts, "finally": True})

@user.message_callback(F.callback.payload == "right", UserStates.wrighting_targets)
@look_if_not_target
async def get_and_wright_targets_in_db_R(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data()
    targets = data.get("targets")
    if not targets:
        await update_menu(context, callback.message, text="Какая то ошибка, попробуй снова:(", attachments=[start_kb]) # type: ignore
        return
    for target in targets:
        await TargetCRUD.create(user_id=callback.from_user.user_id, description=target) # type: ignore
    # Попробуем отредактировать текущее сообщение, иначе отправим новое
    await update_menu(context, callback.message, text="Успешно!", attachments=[start_kb]) # type: ignore
    await context.clear()

@user.message_callback(F.callback.payload == "back_change_target")
@look_if_not_target
async def change_targets(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today()) # type: ignore
    if items == []:
        return
    try:
        await callback.message.edit(text="Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")]) # type: ignore
    await context.set_data({'items': items})

@user.message_callback(F.callback.payload == "target_is_done")
@look_if_not_target
async def make_target_is_done(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today()) # type: ignore
    if items == []:
        return
    # Сохраняем items в context и показываем интерактивную клавиатуру с чекбоксами
    # Попробуем редактировать текущее сообщение — более плавный UX
    # Инициализируем checked set из БД — уже помеченные задачи должны отображаться как ✅
    initial_checked = set()
    for group in items:
        for t in group:
            if getattr(t, 'is_done', False):
                initial_checked.add(t.id)
    await context.set_data({'items': items, 'pending_done': list(initial_checked)})
    # items — формат List[List[Target]]; конвертируем в our Item model defined in kb
    # Собираем модели
    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description))
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты выполнил(а) nf1:", attachments=[inline_keyboard_from_items_with_checks(model_groups, initial_checked, "done")]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что ты выполнил(а) nf1:", attachments=[inline_keyboard_from_items_with_checks(model_groups, initial_checked, "done")]) # type: ignore
    # оставляем состояние прежним (не переключаем стейт)

@user.message_callback(F.callback.payload == "cancel_change_target")
@look_if_not_target
async def cancel_change_targets(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    data = await context.get_data()
    if not data:
        data = await TargetCRUD.get_all_target_today(user_id=callback.from_user.user_id, day=datetime.today()) # type: ignore
    
    answer = ''
    ind = 1
    if isinstance(data, list):
        for i in data:
            for j in i:
                mark = '✅' if getattr(j, 'is_done', False) else '❌'
                answer += f"{ind}. {mark} {j.description}\n"
                ind+=1
    else:
        for a in data.get("items", []): # pyright: ignore[reportAttributeAccessIssue]
            for index, item in enumerate(a):
                mark = '✅' if getattr(item, 'is_done', False) else '❌'
                answer += f"{ind}. {mark} {item.description}\n"
                ind+=1
    await context.clear()
    try:
        await callback.message.edit(text=f"Твои цели на сегодня:\n{answer}", attachments=[change_target]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text=f"Твои цели на сегодня:\n{answer}", attachments=[change_target]) # type: ignore


@user.message_callback(F.callback.payload == "back_to_menu")
@look_if_not_target
async def back_to_menu(callback: MessageCallback, context: MemoryContext):
    """Generic cancel handler: return to main menu and clear ephemeral context."""
    await context.clear()
    try:
        await callback.message.edit(text="Главное меню:", attachments=[start_kb]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Главное меню:", attachments=[start_kb]) # type: ignore

@user.message_callback(F.callback.payload.startswith("item:"))
@look_if_not_target
async def take_id_and_change(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    id = callback.callback.payload
    if not id:
        await update_menu(context, callback.message, text="Ошибка! Хз почему, но айди не вижу(") # type: ignore
        return
    id = id.split(":")[1]
    await context.set_data({"target_id": id})
    try:
        await callback.message.edit(text="Напиши цель снова и я ее изменю (тут можно запятые кста)") # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Напиши цель снова и я ее изменю (тут можно запятые кста)") # type: ignore
    await context.set_state(UserStates.change_targets)

@user.message_callback(F.callback.payload == "back_add_target")
@look_if_not_target
async def add_target(callback: MessageCallback, context: MemoryContext):
    await context.set_state(UserStates.wrighting_targets)
    try:
        sended_message = await callback.message.edit(text=f"Введите дополнительные цели", attachments=[cancel_button_kb])
    except Exception:
        await update_menu(context, callback.message, text=f"Введите дополнительные цели", attachments=[cancel_button_kb])
    # await context.set_data({"mid": sended_message.__repr_args__})

@user.message_callback(F.callback.payload == "back_delete_target")
@look_if_not_target
async def delete_target(callback: MessageCallback, context: MemoryContext):
    # Показать клавиатуру для выбора задач на удаление
    items = await TargetCRUD.get_all_target_today(user_id=callback.from_user.user_id, day=datetime.today()) # type: ignore
    if not items:
        await update_menu(context, callback.message, text="Нет задач для удаления.")
        return

    # Сохраняем items и пустой pending_delete в context
    await context.set_data({'items': items, 'pending_delete': []})

    # Построим model groups
    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description, is_done=getattr(t, 'is_done', False)))
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, set(), "delete")]) # type: ignore
    except Exception:
        try:
            await callback.message.edit(text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, set(), "delete")]) # type: ignore
        except Exception:
            await update_menu(context, callback.message, text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, set(), "delete")]) # type: ignore

@user.message_callback(F.callback.payload.startswith("delete:"))
@look_if_not_target
async def delete_target_callback(callback: MessageCallback, context: MemoryContext):
    payload = callback.callback.payload
    if not payload:
        await update_menu(context, callback.message, text="Не вижу такой задачи:(")
        return
    target_id = int(payload.split(":")[1])

    data = await context.get_data() or {}
    items = data.get('items')
    if not items:
        items = await TargetCRUD.get_all_target_today(user_id=callback.from_user.user_id, day=datetime.today()) # type: ignore

    pending = set(data.get('pending_delete', []))
    if target_id in pending:
        pending.remove(target_id)
    else:
        pending.add(target_id)

    await context.set_data({'items': items, 'pending_delete': list(pending)})

    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description, is_done=getattr(t, 'is_done', False)))
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, pending, "delete")]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Выбери что ты хочешь удалить:", attachments=[inline_keyboard_from_items_for_delete(model_groups, pending, "delete")]) # type: ignore


@user.message_callback(F.callback.payload == "commit_delete")
@look_if_not_target
async def commit_delete_handler(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data() or {}
    pending = list(data.get('pending_delete', []))
    items = data.get('items', [])
    if not pending:
        await update_menu(context, callback.message, text="Нечего удалять.")
        await context.clear()
        return

    # Выполнить bulk delete
    deleted = await TargetCRUD.bulk_delete(pending) # type: ignore
    try:
        await callback.message.edit(text=f"Удалено задач: {deleted}", attachments=[start_kb]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text=f"Удалено задач: {deleted}", attachments=[start_kb]) # type: ignore
    await context.clear()


@user.message_callback(F.callback.payload == "cancel_delete")
@look_if_not_target
async def cancel_delete_handler(callback: MessageCallback, context: MemoryContext):
    await context.clear()
    try:
        await callback.message.edit(text="Отмена удаления.", attachments=[start_kb]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text="Отмена удаления.", attachments=[start_kb]) # type: ignore

@user.message_callback(F.callback.payload.startswith("done:"))
@look_if_not_target
async def take_id_and_change_isdone(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    # Toggle target in pending_done list stored in context, then update the keyboard shown to the user.
    payload = callback.callback.payload
    if not payload:
        await update_menu(context, callback.message, text="Ошибка! Хз почему, но айди не вижу(") # type: ignore
        return
    target_id = int(payload.split(":")[1])

    data = await context.get_data() or {}
    items = data.get('items')
    if not items:
        # reload items from db as fallback
        items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today()) # type: ignore
        await context.set_data({'items': items})

    pending = set(data.get('pending_done', []))
    if target_id in pending:
        pending.remove(target_id)
    else:
        pending.add(target_id)

    await context.set_data({'items': items, 'pending_done': list(pending)})

    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description))
        model_groups.append(row)

    try:
        await callback.message.edit(text="Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items_with_checks(model_groups, pending, "done")]) # type: ignore
    except Exception:
        # fallback to creating/updating the persistent menu when edit is not available
        await update_menu(context, callback.message, text="Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items_with_checks(model_groups, pending, "done")]) # type: ignore

@user.message_created(UserStates.change_targets)
@look_if_not_target
async def change_target_in_db(message: MessageCreated, context: MemoryContext):
    msg = message.message.body.text
    if not msg:
        await update_menu(context, message.message, text="Ошибка! Хз почему, но сообщение не увидел(") # type: ignore
        await context.clear()
        return
    id = await context.get_data()
    id = id.get("target_id", "")
    if id == "":
        await update_menu(context, message.message, text="Ошибка! Хз почему, но айди таски не увидел(") # type: ignore
        await context.clear()
        return
    
    await TargetCRUD.update(target_id=id, description=msg)
    await message.message.answer("Готово!")
    items = await TargetCRUD.get_all_target_today(message.from_user.user_id, datetime.today()) # type: ignore
    if items == []:
        print("На ретерн попали")
        return
    await message.message.answer("Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")]) # type: ignore
    await context.set_data({"items": items})

# Коммит и отмена для пометки выполненных задач

@user.message_callback(F.callback.payload == "commit_done")
@look_if_not_target
async def commit_done_handler(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data() or {}
    pending = set(data.get('pending_done', []))
    items = data.get('items', [])
    if not items:
        await update_menu(context, callback.message, text="Нет задач для подтверждения.") # type: ignore
        await context.clear()
        return

    # Применяем изменения к БД: для каждой задачи из items — если её id в pending, отмечаем is_done=True, иначе оставляем без изменений
    # Чтобы минимизировать число запросов — обновляем только выбранные
    applied = 0
    for group in items:
        for t in group:
            if t.id in pending and not t.is_done:
                await TargetCRUD.update(target_id=t.id, is_done=True) # type: ignore
                applied += 1

    # Применяем изменения: синхронизируем состояния is_done так, как указано в pending (desired)
    desired = pending
    applied = 0
    removed = 0
    for group in items:
        for t in group:
            if t.id in desired and not t.is_done:
                await TargetCRUD.update(target_id=t.id, is_done=True) # type: ignore
                applied += 1
            if t.id not in desired and t.is_done:
                await TargetCRUD.update(target_id=t.id, is_done=False) # type: ignore
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

    await update_menu(context, callback.message, text=msg, attachments=[start_kb]) # type: ignore
    await context.clear()


@user.message_callback(F.callback.payload == "cancel_done")
@look_if_not_target
async def cancel_done_handler(callback: MessageCallback, context: MemoryContext):
    # Просто откатываем изменения и убираем временную клавиатуру
    await context.clear()
    await update_menu(context, callback.message, text="Отменено.", attachments=[start_kb]) # type: ignore

@user.message_callback(F.callback.payload == "start_session")
@look_if_not_target
async def start_session_choose_target(message: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, message.message, text="У тебя уже открыта сессия...", attachments=[stop_kb])
        return

    # 1. Получаем цели на сегодня
    targets_raw = await TargetCRUD.get_all_target_today(message.from_user.user_id, datetime.today()) # type: ignore

    # Распаковываем вложенный список
    targets = [item for sublist in targets_raw for item in sublist]

    if not targets:
        await update_menu(context, message.message, text="Сначала нужно добавить цели на сегодня. Нажмите 'Цели 🧠'", attachments=[start_kb])
        return

    # 2. Показываем клавиатуру для выбора
    # Конвертируем цели в формат для клавиатурыƒ
    items_for_kb = [[Item(id=t.id, description=t.description) for t in targets]]

    await update_menu(
        context,
        message.message,
        text="Выбери цель, над которой начинаешь работать:",
        attachments=[inline_keyboard_from_items(items_for_kb, "start_target")]
    )
    await context.set_state(UserStates.choosing_target_for_session)

@user.message_callback(F.callback.payload.startswith("start_target:"), UserStates.choosing_target_for_session)
async def start_going(callback: MessageCallback, context: MemoryContext):
    target_id_str = callback.callback.payload.split(":")[1]
    if not target_id_str.isdigit():
        await update_menu(context, callback.message, text="Ошибка! Неверный ID цели.", attachments=[start_kb])
        await context.clear()
        return

    target_id = int(target_id_str)

    session = await SessionCRUD.get_active_session(callback.from_user.user_id)
    if session:
        await update_menu(context, callback.message, text="У тебя уже открыта сессия...", attachments=[stop_kb])
        return

    now = datetime.now(UTC_PLUS_3)
    await SessionCRUD.create(
        user_id=callback.from_user.user_id,
        target_id=target_id,
        date_start=now,
        date_end=now,
        is_active=True
    )
    await context.set_state(UserStates.counted_time)
    await update_menu(context, callback.message, text=f"Фиксирую старт... {now.strftime('%H:%M:%S')}", attachments=[stop_kb])

@user.message_callback(F.callback.payload == "stop_session", UserStates.counted_time)
@look_if_not_target
async def stop_going(message: MessageCallback, context: MemoryContext):
    await context.clear()

    now = datetime.now(UTC_PLUS_3)
    now = now.replace(tzinfo=None)

    session = await SessionCRUD.get_active_session(message.from_user.user_id)
    if not session:
        await update_menu(context, message.message, text="Ошибка! Не вижу активной сессии.", attachments=[start_kb])
        return

    await SessionCRUD.update(session_id=session.id, date_end=now, is_active=False)
        
    elapsed = now - session.date_start
    await UserCRUD.add_duration(message.from_user.user_id, elapsed)

    elapsed_str = format_duration(elapsed)
    await update_menu(context, message.message, text=f"Сессия завершена. Добавлено: `{elapsed_str}`", attachments=[start_kb])


async def draw_profile(message: MessageCallback, context:MemoryContext):
    user_data = await UserCRUD.get_by_tid(message.from_user.user_id)

    today = datetime.now(UTC_PLUS_3).date()

    time_today = await SessionCRUD.total_active_time_on_date(user_data.tid, today)
    time_week = await SessionCRUD.get_total_time_for_week(user_data.tid, today)

    next_level = None

    lp = get_levels_config()
    for i in sorted(lp.keys(), key=int):
        if int(user_data.points) < int(i):
            next_level = int(i)
            break

    answer = (
        f"👤 *{user_data.name}, {user_data.level} уровень*\n"
        f"📈 Поинтов: {user_data.points}, до следующего уровня {next_level - int(user_data.points)}\n\n"
        f"⏱️ *Активность:*\n"
        f"За сегодня: *{format_duration(time_today)}*\n"
        f"За неделю: *{format_duration(time_week)}*\n"
        f"Всего: *{format_total_duration(user_data.count_time)}*\n\n"
        f"🎯 *Время по целям:*"
    )

    targets_raw = await TargetCRUD.list_by_user(user_data.tid)

    targets_with_time = []
    for target in targets_raw:
        target_time = await SessionCRUD.get_total_time_for_target(target.id)
        targets_with_time.append((target, format_duration(target_time)))

    profile_kb = create_profile_targets_keyboard(targets_with_time)
    user_state = await context.get_state()
    print(user_state)
    if str(user_state) == "UserStates:draw_new_prifile":
        await message.message.answer(text=answer, attachments=[profile_kb])
        context.clear()
    else:
        await update_menu(context, message.message, text=answer, attachments=[profile_kb])

@user.message_callback(F.callback.payload == "get_profile")
@look_if_not_target
async def get_profile(message: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, message.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id) # type: ignore
        if session:
            await context.set_state(UserStates.counted_time)
            await update_menu(context, message.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb])
            return
    await draw_profile(message, context)

@user.message_callback(F.callback.payload.startswith("adjust_time:"))
async def adjust_target_time_start(callback: MessageCallback, context: MemoryContext):
    target_id_str = callback.callback.payload.split(":")[1]
    if not target_id_str.isdigit():
        return

    target_id = int(target_id_str)
    target = await TargetCRUD.get_by_id(target_id)
    if not target:
        await callback.answer("Цель не найдена!")
        return

    await context.set_data({"adjust_target_id": target_id})
    await context.set_state(UserStates.adjusting_target_time)

    prompt = (
        f"Введите время для добавления к цели:\n"
        f"*{target.description}*\n\n"
        f"Формат: `чч:мм:сс`. Для вычитания используйте минус, например `-00:10:00`."
    )

    await update_menu(context, callback.message, text=prompt, attachments=[back_to_profile_kb])

@user.message_created(UserStates.adjusting_target_time)
@look_if_not_target
async def adjust_target_time_finish(message: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    target_id = data.get("adjust_target_id")
    if not target_id:
        await context.clear()
        return

    text_time = message.message.body.text
    seconds = hhmmss_to_seconds(text_time)

    if seconds is None:
        await message.message.answer("Неверный формат времени. Попробуйте еще раз (чч:мм:сс).")
        return

    now = datetime.now(UTC_PLUS_3)
    duration = timedelta(seconds=seconds)

    user_updated = await UserCRUD.add_duration(message.from_user.user_id, duration)
    if not user_updated:
        await update_menu(context, message.message, text="Ошибка! Не удалось обновить профиль.", attachments=[start_kb])
        await context.clear()
        return

    await SessionCRUD.create(
        user_id=user_updated.tid,
        target_id=target_id,
        date_start=now,
        date_end=now + duration,
        is_active=False
    )

    await context.clear()
    await message.message.answer("Время успешно обновлено!")

    await context.set_state(UserStates.draw_new_prifile)
    await get_profile(message, context)

@user.message_callback(F.callback.payload == "change_time")
@look_if_not_target
async def change_sum_time(callback: MessageCallback, context: MemoryContext):
    prompt = (
        "Напиши время, которое нужно прибавить в формате чч:мм:сс\n\n"
        "Если хочешь убавить, то в формате чч:мм:-сс, важно, чтобы '-' был приписан к ненулевому числу, чтобы вычесть ровно минуту, нужно написать 00:-01:00"
    )
    try:
        await callback.message.edit(text=prompt, attachments=[back_to_profile_kb]) # type: ignore
    except Exception:
        await update_menu(context, callback.message, text=prompt, attachments=[back_to_profile_kb]) # type: ignore
    await context.set_state(UserStates.take_time)

@user.message_created(UserStates.take_time)
@look_if_not_target
async def get_time(message: MessageCreated, context: MemoryContext):

    text = message.message.body.text
    time = hhmmss_to_seconds(text) # type: ignore
    if time is None:
        await update_menu(context, message.message, text="Какая то ошибка.. Попробуй снова", attachments=[change_time_activity_kb])
        return
    res = await UserCRUD.add_duration(message.from_user.user_id, time) # type: ignore
    if res is None:
        await update_menu(context, message.message, text="Какая то ошибка.. Попробуй снова", attachments=[change_time_activity_kb])
        return 
    
    await draw_profile(message, context)

    await context.clear()
    
@user.message_callback(F.callback.payload == "get_targets")
@look_if_not_target
async def get_targets(message: MessageCreated, context: MemoryContext):
    target = await TargetCRUD.get_all_target_today(message.from_user.user_id, datetime.today()) # type: ignore
    if target == []:
        await update_menu(context, message.message, text="Почему то не вижу твоих целей на сегодня(\nВозможно ты их просто не написал(а)..(в общем где-то моя ошибка)\n\nНапиши их прямо сейчас, ловлю!")
        await context.set_state(UserStates.wrighting_targets)
        return
    answer = ''
    ind = 1
    for a in target:
        for index, item in enumerate(a):
            mark = '✅' if getattr(item, 'is_done', False) else '❌'
            answer += f"{ind}. {mark} {item.description}\n"
            ind+=1
    await update_menu(context, message.message, text=f"Твои цели на сегодня:\n{answer}", attachments=[change_target])
    await context.set_data({"items": target})

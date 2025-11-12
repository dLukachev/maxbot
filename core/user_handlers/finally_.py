from datetime import datetime
from maxapi import Router, F
from maxapi.types import MessageCreated, MessageCallback, Command
from maxapi.context import MemoryContext
import logging

from utils.states import UserStates
from core.user_handlers.kb import (
    stop_kb,
    Item,
    inline_keyboard_from_items_with_checks_finally,
    checking_done_target_kb,
    create_new_target_kb
)

from utils.message_utils import update_menu
from core.database.requests import TargetCRUD, UserCRUD

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

user_finally = Router()

@user_finally.message_callback(F.callback.payload == "target_is_done_finally")
async def make_target_is_done_finally(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        return
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today()) # type: ignore
    if not items:
        try:
            await callback.message.edit("Целей нет:( СТАВЬ!!!", attachments=[])
        except Exception:
            await callback.message.answer("Целей нет:( СТАВЬ!!!", attachments=[])
        return

    initial_checked = set()
    for group in items:
        for t in group:
            if getattr(t, 'is_done', False):
                initial_checked.add(t.id)
    await context.set_data({'items': items, 'pending_done': list(initial_checked)})

    model_groups = []
    for group in items:
        row = []
        for t in group:
            row.append(Item(id=t.id, description=t.description))
        model_groups.append(row)

    try:
        try:
            await callback.message.edit(text="Выбери что ты выполнил(а) f:", attachments=[inline_keyboard_from_items_with_checks_finally(model_groups, initial_checked, "finally_done")]) # type: ignore
        except Exception:
            await update_menu(context, callback.message, text="Выбери что ты выполнил(а) f:", attachments=[
                inline_keyboard_from_items_with_checks_finally(model_groups, initial_checked,"finally_done")])  # type: ignore
    except Exception:
        await callback.message.answer(context, callback.message, text="Выбери что ты выполнил(а) f:", attachments=[inline_keyboard_from_items_with_checks_finally(model_groups, initial_checked, "finally_done")]) # type: ignore

@user_finally.message_callback(F.callback.payload.startswith("finally_done:"))
async def take_id_and_change_finally_isdone(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await update_menu(context, callback.message, text="Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        return
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
        await callback.message.edit(text="Выбери что ты выполнил(а) f1:", attachments=[inline_keyboard_from_items_with_checks_finally(model_groups, pending, "finally_done")]) # type: ignore
    except Exception:
        # fallback to creating/updating the persistent menu when edit is not available
        await update_menu(context, callback.message, text="Выбери что ты выполнил(а) f1:", attachments=[inline_keyboard_from_items_with_checks_finally(model_groups, pending, "finally_done")]) # type: ignore

@user_finally.message_callback(F.callback.payload == "commit_finally_done")
async def commit_done_handler_finally(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data() or {}
    pending = set(data.get('pending_done', []))
    items = data.get('items', [])
    if not items:
        # TODO: тут потенциально может быть ошибка, добавить кб с отменой(кнопкой назад)
        await update_menu(context, callback.message, text="Нет задач для подтверждения.") # type: ignore
        await context.clear()
        return

    # Применяем изменения к БД: для каждой задачи из items — если её id в pending, отмечаем is_done=True, иначе оставляем без изменений,
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
    await context.clear()
    try:
        await callback.message.edit("Теперь пора ставить новые цели, жми кнопку как будешь готов", attachments=[create_new_target_kb])
    except Exception:
        await callback.message.answer("Теперь пора ставить новые цели, жми кнопку как будешь готов", attachments=[create_new_target_kb])

# TODO: обработка отмена cancel_change_finally_target
# должна быть отправка сообщения
# text="Вот и закончился день, начался новый, пора отмечать что сделал, а что нет!"
@user_finally.message_callback(F.callback.payload == "cancel_change_finally_target")
async def cancel_change_finally_target(callback: MessageCallback, context: MemoryContext):
    try:
        await update_menu(context, callback.message, text='Если ничего не забыл отметить, то жми "готово"!', attachments=[checking_done_target_kb])  # type: ignore
    except Exception:
        await callback.message.answer('Если ничего не забыл отметить, то жми "готово"!', attachments=[checking_done_target_kb])

# TODO: обработка кнопки day_is_done_finally
# тут отдается приказ сделать расчеты по поинтам,
# а так же отправить сообщение с кнопкой, чтобы поставить новые цели
@user_finally.message_callback(F.callback.payload == "day_is_done_finally")
async def day_is_done_finally(callback: MessageCallback, context: MemoryContext):
    # ОТДАТЬ ПРИКАЗ РАССЧИТАТЬ ПОИНТЫ!!!!!
    try:
        await update_menu(context, callback.message, text="Теперь пора ставить новые цели, жми кнопку как будешь готов", attachments=[create_new_target_kb])  # type: ignore
    except Exception:
        await callback.message.answer("Теперь пора ставить новые цели, жми кнопку как будешь готов", attachments=[create_new_target_kb])


@user_finally.message_callback(F.callback.payload == "create_new_target")
async def create_new_target(callback: MessageCallback, context: MemoryContext):
    try:
        await callback.message.edit("Ловлю, а ты пиши")
    except Exception:
        await callback.message.answer("Ловлю, а ты пиши")
    await context.set_state(UserStates.wrighting_targets)
    await context.set_data({"finally": True})
from datetime import datetime
from maxapi import Router, F
from maxapi.types import MessageCreated, MessageCallback, Command
from maxapi.context import MemoryContext

from utils.states import FirstStates, UserStates
from core.user_handlers.kb import wright_target, confirmation, start_kb, stop_kb, change_target, inline_keyboard_from_items
from utils.random_text import get_text
from core.database.requests import UserCRUD, TargetCRUD, SessionCRUD
from utils.redis import get_redis_async, get_state_r, set_state_r, delete_state_r
from utils.dates import UTC_PLUS_3, format_total_duration
from utils.cfg_points import get_levels_config

user = Router()
redis = get_redis_async()

# ----------------- COMMANDS -----------------

# Приветственное сообщение, сразу после него кидаем на написание целей, естественно
# после нажатия на кнопку
@user.message_created(Command("start"))
async def send_info(message: MessageCreated, context: MemoryContext):
    # смотрим есть ли такой юзер в бд
    checking = await UserCRUD.get_by_tid(message.from_user.user_id) # pyright: ignore[reportOptionalMemberAccess]
    # если нет, то создаем и идем по сценарию нового пользователя
    if not checking:
        await UserCRUD.create(tid=message.from_user.user_id, name=message.from_user.first_name, username=message.from_user.username) # pyright: ignore[reportOptionalMemberAccess]
        await message.message.answer(f"Привет, {message.from_user.first_name}! Ты попал куда надо, рассказываю. Смысл этого бота в том, чтобы помочь тебе не забывать кратковременные цели и отслеживать их выполнение, а так же напоминать об отдыхе) Информацию, что я могу сделать для тебя, можешь получить в меню, мы туда скоро доберемся") # type: ignore
        await message.message.answer("А пока напиши свою цель(и): ", attachments=[wright_target])
        await context.set_state(FirstStates.wait_on_click_on_first_button)
    # иначе показываем ему текущий интерфейс исходя из его состояния
    else:
        await message.message.answer("%", attachments=[start_kb])

@user.message_created(F.text, FirstStates.wait_on_click_on_first_button)
async def blocker(message: MessageCreated):
    """Блокируем любые текстовые сообщения на момент FirstStates.wait_on_click_on_first_button, 
    потом это нигде не используется
    """
    pass

# ----------------- CALLBACK -----------------

# @user.message_callback()
# async def debug_cb(event: MessageCallback):
#     print("DEBUG payload =", event.callback.payload)
#     await event.message.answer(text=f"payload={event.callback.payload}")

@user.message_callback(F.callback.payload.in_({"back_wright_target", "not_right"}))
async def wrt_in_db(callback: MessageCallback, context: MemoryContext):
    current = await context.get_state()
    text = get_text("instructions_for_wrighting")

    if current == "FirstStates:wait_on_click_on_first_button":
        await context.clear()

    if current == "UserStates:counted_time":
        await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    else:
        session = await SessionCRUD.get_active_session(callback.from_user.user_id) # type: ignore
        if session:
            await context.set_state(UserStates.counted_time)
            await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
            return

    if text and callback.callback.payload == "back_wright_target":
        await callback.message.answer(text) # type: ignore
    elif callback.callback.payload == "back_change_target":
        await callback.message.answer(get_text("instructions_for_wrighting")) # type: ignore
    
    await context.set_state(UserStates.wrighting_targets)
    await callback.message.delete()

@user.message_created(UserStates.wrighting_targets)
async def get_and_wright_targets_in_db(message: MessageCreated, context: MemoryContext):
    texts = message.message.body.text # type: ignore
    answer = ""
    index = 1
    if texts is not None:
        texts = texts.replace(", ", ",").split(",")
        for text in texts:
            answer += f"{index}. {text}\n"
            index += 1

        await message.message.delete()
        await message.message.answer(f"Твой список:\n{answer}\nВерно?", attachments=[confirmation]) # type: ignore
        await context.set_data({"targets": texts})

@user.message_callback(F.callback.payload == "right", UserStates.wrighting_targets)
async def get_and_wright_targets_in_db_R(callback: MessageCallback, context: MemoryContext):
    data = await context.get_data()
    targets = data.get("targets")
    if not targets:
        await callback.message.answer("Какая то ошибка, попробуй снова:(") # type: ignore
        await callback.message.delete() # type: ignore
        return
    for target in targets:
        await TargetCRUD.create(user_id=callback.from_user.user_id, description=target) # type: ignore
    await callback.message.delete() # type: ignore
    await callback.message.answer("Успешно!", attachments=[start_kb]) # type: ignore
    await context.clear()

@user.message_callback(F.callback.payload == "back_change_target")
async def change_targets(callback: MessageCallback, context: MemoryContext):
    # здесь должно происходить измененеие сообщения, 
    # чтобы появилась другая клава + кнопка отмены
    # Так же тут нужно передавать все сегодняшние цели, 
    # а еще нужно сделать добавление:)))))
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today()) # type: ignore
    if items == []:
        return
    await callback.message.delete() # type: ignore
    await callback.message.answer("Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")]) # type: ignore
    await context.set_data({'items': items})

@user.message_callback(F.callback.payload == "target_is_done")
async def meke_target_is_done(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    items = await TargetCRUD.get_all_target_today(callback.from_user.user_id, datetime.today()) # type: ignore
    if items == []:
        return
    await callback.message.delete() # type: ignore
    await callback.message.answer("Выбери что ты выполнил(а):", attachments=[inline_keyboard_from_items(items, "item")]) # type: ignore
    await context.set_data({'items': items})

@user.message_callback(F.callback.payload == "cancel_change_target")
async def cancel_change_targets(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        await context.set_state(UserStates.counted_time)
        return
    data = await context.get_data()
    if not data:
        await callback.message.answer("Какая-то ошибка:(") # type: ignore
        await callback.message.delete() # type: ignore
        await context.clear()
        return
    await callback.message.delete() # type: ignore
    answer = ''
    ind = 1
    for a in data.get("items", []):
        for index, item in enumerate(a):
            answer += f"{ind}. {item.description}\n"
            ind+=1
    await callback.message.answer(f"Твои цели на сегодня:\n{answer}", attachments=[change_target]) # type: ignore

@user.message_callback(F.callback.payload.startswith("item:"))
async def take_id_and_change(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        
        return
    id = callback.callback.payload
    if not id:
        await callback.message.answer("Ошибка! Хз почему, но айди не вижу(") # type: ignore
        return
    id = id.split(":")[1]
    await context.set_data({"target_id": id})
    await callback.message.answer("Напиши цель снова и я ее изменю (тут можно запятые кста)") # type: ignore
    await context.set_state(UserStates.change_targets)

@user.message_callback(F.callback.payload.startswith("done:"))
async def take_id_and_change_isdone(callback: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await callback.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb]) # type: ignore
        return
    id = callback.callback.payload
    if not id:
        await callback.message.answer("Ошибка! Хз почему, но айди не вижу(") # type: ignore
        return
    id = id.split(":")[1]
    target = await TargetCRUD.get_by_id(id) # type: ignore
    if not target:
        await callback.message.answer("Такой цели не вижу(:)") # type: ignore
        return
    isdone_ = True if target.is_done == False else False
    await TargetCRUD.update(target_id=id, is_done=isdone_) # type: ignore

@user.message_created(UserStates.change_targets)
async def change_target_in_db(message: MessageCreated, context: MemoryContext):
    msg = message.message.body.text
    if not msg:
        await message.message.answer("Ошибка! Хз почему, но сообщение не увидел(") # type: ignore
        await context.clear()
        return
    id = await context.get_data()
    id = id.get("target_id", "")
    if id == "":
        await message.message.answer("Ошибка! Хз почему, но айди таски не увидел(") # type: ignore
        await context.clear()
        return
    
    await TargetCRUD.update(target_id=id, description=msg)
    await context.clear()
    await message.message.answer("Готово!")
    items = await TargetCRUD.get_all_target_today(message.from_user.id, datetime.today()) # type: ignore
    if items == []:
        return
    await message.message.delete() # type: ignore
    await message.message.answer("Выбери что хочешь изменить:", attachments=[inline_keyboard_from_items(items, "item")]) # type: ignore
    await context.set_data({"items": items})

# ----------------- TEXT -----------------

@user.message_callback(F.callback.payload == "start_session")
async def start_going(message: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time": # type: ignore
        await message.message.answer("У тебя уже открыта сессия...", attachments=[stop_kb])
        await context.set_state(UserStates.counted_time)
        # await set_state_r(redis, message.from_user.id, 'go') # type: ignore
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id) # type: ignore
        if not session:
            now = datetime.now(UTC_PLUS_3)
            await SessionCRUD.create(user_id=message.from_user.user_id, date_start=now, date_end=now, is_active=True) # type: ignore
            # await set_state_r(redis, message.from_user.id, 'go') # type: ignore
            await context.set_state(UserStates.counted_time)
            await message.message.answer(f"Фиксирую старт... {now.strftime('%m-%d %H:%M:%S')}", attachments=[stop_kb])


@user.message_callback(F.callback.payload == "stop_session", UserStates.counted_time)
async def stop_going(message: MessageCallback, context: MemoryContext):
    await context.clear()

    now = datetime.now(UTC_PLUS_3)
    now = now.replace(tzinfo=None)

    session = await SessionCRUD.get_active_session(message.from_user.user_id) # type: ignore

    await SessionCRUD.update(session_id=session.id, date_end=now, is_active=False) # type: ignore
        
    # суммируем в профиле пользователя
    elapsed = now - session.date_start # type: ignore
    await UserCRUD.add_duration(message.from_user.user_id, elapsed) # type: ignore

    # удаляем запись стейта (временно откл)
    # await delete_state_r(redis, message.from_user.id) # type: ignore

    # красиво выводим
    total_seconds = int(elapsed.total_seconds())
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    await message.message.answer(f"Добавлено: `{h:02d}:{m:02d}:{s:02d}`", attachments=[start_kb])


@user.message_callback(F.callback.payload == "get_profile")
async def get_profile(message: MessageCallback, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await message.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb])
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id) # type: ignore
        if session:
            await context.set_state(UserStates.counted_time)
            await message.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb])
            return
    
    user_data = await UserCRUD.get_by_tid(message.from_user.user_id) # type: ignore
    next_level = None
    # Находим минимальный порог, который больше текущих поинтов пользователя
    lp = get_levels_config()
    for i in sorted(lp.keys(), key=int):
        if int(user_data.points) < int(i): # type: ignore
            next_level = int(i)
            break
    
    answer = f"{user_data.name}, {user_data.level} уровень.\n" # type: ignore
    if next_level is not None:
        answer += f"Поинтов: {user_data.points}, до следующего уровня {next_level - int(user_data.points)}\n" # type: ignore
    else:
        answer += f"Поинтов: {user_data.points} (максимальный уровень достигнут!)\n" # type: ignore
    answer += f"Общее время активности: {format_total_duration(user_data.count_time)}" # type: ignore

    await message.message.answer(answer)
    
@user.message_callback(F.callback.payload == "get_targets")
async def get_targets(message: MessageCreated, context: MemoryContext):
    user_state = await context.get_state()
    if user_state == "UserStates:counted_time":
        await message.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb])
        return
    else:
        session = await SessionCRUD.get_active_session(message.from_user.user_id) # type: ignore
        if session:
            await context.set_state(UserStates.counted_time)
            await message.message.answer("Сначала заверши подсчет времени!", attachments=[stop_kb])
            return
    
    target = await TargetCRUD.get_all_target_today(message.from_user.user_id, datetime.today()) # type: ignore
    if target == []:
        await message.message.answer("Почему то не вижу твоих целей на сегодня(\nВозможно ты их просто не написал(а)..(в общем где-то моя ошибка)\nМожешь это сделать прямо сейчас!")
        await context.set_state(UserStates.wrighting_targets)
        return
    answer = ''
    ind = 1
    for a in target:
        for index, item in enumerate(a):
            answer += f"{ind}. {item.description}\n"
            ind+=1
    await message.message.answer(f"Твои цели на сегодня:\n{answer}", attachments=[change_target])

    
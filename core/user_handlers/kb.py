from typing import List
from maxapi.types import CallbackButton, ChatButton  # Только эти импортируем
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from utils.random_text import get_text


class Item:
    """Модель элемента (цель, задача и т.д.)"""
    def __init__(self, id: int, description: str, is_done: bool = False):
        self.id = id
        self.description = description
        self.is_done = is_done


def inline_keyboard_from_items(items: List[List[Item]], callback_prefix: str):
    """
    Динамическая inline-клавиатура из списка items.
    - items: List[List[Item]] — группы кнопок по строкам
    - callback_prefix: префикс для callback_data (например, 'select')
    Добавляет кнопку "Отмена" внизу.
    """
    kb = InlineKeyboardBuilder()

    if not items:
        kb.row(
            CallbackButton(text="Ошибка!", payload="ERROR")
        )
        return kb.as_markup()

    index = 1
    for group in items:
        row = []
        for item in group:
            row.append(
                CallbackButton(
                    text=f"{index}. {item.description}",
                    payload=f"{callback_prefix}:{item.id}"
                )
            )
            index += 1
        if row:
            kb.row(*row)

    # Кнопка "Отмена"
    kb.row(CallbackButton(text="Отмена", payload="cancel_change_target"))

    return kb.as_markup()


def inline_keyboard_from_items_with_checks(items: List[List[Item]], checked_ids: set[int], callback_prefix: str):
    """
    Построить inline-клавиатуру где у каждой кнопки есть чекбокс, отражающий checked_ids.
    checked_ids: set of target.id, отмеченные как выбранные (готовые).
    callback_prefix: префикс для payload — например 'done' или 'select'.
    Внизу добавляем кнопки Готово (commit) и Отмена (cancel_done).
    """
    kb = InlineKeyboardBuilder()

    if not items:
        kb.row(
            CallbackButton(text="Ошибка!", payload="ERROR")
        )
        return kb.as_markup()

    index = 1
    for group in items:
        row = []
        for item in group:
            # use ✅ for done and ❌ for not done
            checked = "✅ " if item.id in checked_ids else "❌ "
            row.append(
                CallbackButton(
                    text=f"{checked}{index}. {item.description}",
                    payload=f"{callback_prefix}:{item.id}"
                )
            )
            index += 1
        if row:
            kb.row(*row)

    # Контролы внизу: Готово (commit) и Отмена
    kb.row(
        CallbackButton(text="Готово", payload="commit_done"),
        CallbackButton(text="Отмена", payload="cancel_done")
    )

    return kb.as_markup()


def inline_keyboard_from_items_for_delete(items: List[List[Item]], selected_ids: set[int], callback_prefix: str):
    """
    Построить inline-клавиатуру для выбора на удаление. Показывает '🗑️' для выбранных и '❌' для не выбранных.
    Внизу добавляет кнопки "Удалить" (commit_delete) и "Отмена" (cancel_delete).
    """
    kb = InlineKeyboardBuilder()

    if not items:
        kb.row(CallbackButton(text="Ошибка!", payload="ERROR"))
        return kb.as_markup()

    index = 1
    for group in items:
        row = []
        for item in group:
            # If item already done, show ✅ as secondary indicator; selection for deletion overrides marker
            sel_mark = "🗑️ " if item.id in selected_ids else ("✅ " if getattr(item, 'is_done', False) else "❌ ")
            row.append(
                CallbackButton(text=f"{sel_mark}{index}. {item.description}", payload=f"{callback_prefix}:{item.id}")
            )
            index += 1
        if row:
            kb.row(*row)

    kb.row(
        CallbackButton(text="Удалить", payload="commit_delete"),
        CallbackButton(text="Отмена", payload="cancel_delete")
    )

    return kb.as_markup()

def change_time_activity():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Изменить общее время", payload="change_time")) # type: ignore
    # Добавляем кнопку Отмена, чтобы можно было вернуться в главное меню
    kb.row(CallbackButton(text="Отмена", payload="back_to_menu")) # type: ignore
    return kb.as_markup()

change_time_activity_kb = change_time_activity()

def cancel_button():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Отмена", payload="cancel_change_target")) # type: ignore
    return kb.as_markup()

cancel_button_kb = cancel_button()

def create_wright_target_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text=get_text('wright_target'), payload="back_wright_target")) # type: ignore
    # кнопка отмены возвращает на уровень выше (в главное меню)
    kb.row(CallbackButton(text="Отмена", payload="back_to_menu")) # type: ignore
    return kb.as_markup()

wright_target = create_wright_target_keyboard()


def create_change_target_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Добавить", payload="back_add_target"))
    kb.row(CallbackButton(text="Изменить цели", payload="back_change_target"))
    kb.row(CallbackButton(text="Удалить", payload="back_delete_target"))
    kb.row(CallbackButton(text="Отметить выполненное", payload="target_is_done"))
    # Добавляем Отмена, чтобы вернуться в главное меню
    kb.row(CallbackButton(text="Отмена", payload="back_to_menu"))
    return kb.as_markup()

change_target = create_change_target_keyboard()


def create_confirmation_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Да", payload="right"))
    kb.row(CallbackButton(text="Нет", payload="not_right"))
    # Отмена — возврат в главное меню
    kb.row(CallbackButton(text="Отмена", payload="back_to_menu"))
    return kb.as_markup()

confirmation = create_confirmation_keyboard()


# === Reply-клавиатуры ===

def create_start_keyboard():
    """Основная стартовая клавиатура."""
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text='Начать 🎯', payload='start_session'),
        CallbackButton(text='Профиль 👤', payload='get_profile'),
        CallbackButton(text='Цели 🧠', payload='get_targets')
    )
    return kb.as_markup()

start_kb = create_start_keyboard()

def create_stop_keyboard():
    """Клавиатура для остановки."""
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text='Стоп ❌', payload='stop_session'),
        CallbackButton(text='Профиль 👤', payload='get_profile'),
        CallbackButton(text='Цели 🧠', payload='get_targets')
    )
    return kb.as_markup()

stop_kb = create_stop_keyboard()
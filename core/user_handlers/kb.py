from typing import List
from maxapi.types import CallbackButton, ChatButton  # Только эти импортируем
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from utils.random_text import get_text


class Item:
    """Модель элемента (цель, задача и т.д.)"""
    def __init__(self, id: int, description: str):
        self.id = id
        self.description = description


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


# === Статические клавиатуры через Builder ===

def create_wright_target_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text=get_text('wright_target'), payload="back_wright_target")) # type: ignore
    return kb.as_markup()

wright_target = create_wright_target_keyboard()


def create_change_target_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Изменить цели", payload="back_change_target"))
    kb.row(CallbackButton(text="Отметить выполненное", payload="target_is_done"))
    return kb.as_markup()

change_target = create_change_target_keyboard()


def create_confirmation_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Да", payload="right"))
    kb.row(CallbackButton(text="Нет", payload="not_right"))
    return kb.as_markup()

confirmation = create_confirmation_keyboard()


# === Reply-клавиатуры ===

def create_start_keyboard():
    """Основная стартовая клавиатура."""
    kb = InlineKeyboardBuilder()
    kb.row(
        ChatButton(text='Начать 🎯', chat_title='Начать 🎯'),
        ChatButton(text='Профиль 👤', chat_title='Профиль 👤'),
        ChatButton(text='Цели 🧠', chat_title='Цели 🧠')
    )
    return kb.as_markup()

start_kb = create_start_keyboard()

def create_stop_keyboard():
    """Клавиатура для остановки."""
    kb = InlineKeyboardBuilder()
    kb.row(
        ChatButton(text='Стоп ❌', chat_title='Стоп ❌'),
        ChatButton(text='Профиль 👤', chat_title='Профиль 👤'),
        ChatButton(text='Цели 🧠', chat_title='Цели 🧠')
    )
    return kb.as_markup()

stop_kb = create_stop_keyboard()
# Состояния для принятия сообщений от пользователя
from maxapi.context import State, StatesGroup

class FirstStates(StatesGroup):
    wait_on_click_on_first_button = State()

class UserStates(StatesGroup):
    wrighting_targets = State()
    change_targets = State()
    counted_time = State()
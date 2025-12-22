from aiogram.fsm.state import StatesGroup, State

class Registration(StatesGroup):
    waiting_for_phone = State()

class AdminStates(StatesGroup):
    browsing = State()
    waiting_for_media = State()
    broadcasting = State()

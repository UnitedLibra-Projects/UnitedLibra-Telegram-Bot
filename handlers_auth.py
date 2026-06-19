import re
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from auth_storage import UsersStorage
from config import Settings

router = Router(name="auth")

LOGIN_TEXT = "Войти"
REGISTER_TEXT = "Зарегистрироваться"
LOGOUT_TEXT = "Выйти"
CANCEL_TEXT = "Отмена"

AUTHORIZED_USERS: set[int] = set()
LOGIN_PATTERN = re.compile(r"^[^\s]{3,32}$")
STORAGES: dict[str, UsersStorage] = {}


class RegistrationStates(StatesGroup):
    # Шаги регистрации
    waiting_full_name = State()
    waiting_login = State()
    waiting_password = State()


class LoginStates(StatesGroup):
    # Шаги входа
    waiting_login = State()
    waiting_password = State()


def get_start_keyboard() -> ReplyKeyboardMarkup:
    # Клавиатура входа
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=LOGIN_TEXT), KeyboardButton(text=REGISTER_TEXT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    # Клавиатура главного меню
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Книги"), KeyboardButton(text="Авторы")],
            [KeyboardButton(text="Категории"), KeyboardButton(text="Издатели")],
            [KeyboardButton(text=LOGOUT_TEXT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите таблицу",
    )


def authorize_user(user_id: int) -> None:
    # Выдача доступа
    AUTHORIZED_USERS.add(user_id)


def deauthorize_user(user_id: int) -> None:
    # Сброс доступа
    AUTHORIZED_USERS.discard(user_id)


def is_authorized(user_id: int) -> bool:
    # Проверка доступа
    return user_id in AUTHORIZED_USERS


def is_valid_login(login: str) -> bool:
    # Проверка логина
    return bool(LOGIN_PATTERN.fullmatch(login))


def get_storage(settings: Settings) -> UsersStorage:
    # Получение хранилища пользователей
    storage_path = str(Path(settings.USERS_STORAGE_PATH).resolve())

    if storage_path not in STORAGES:
        STORAGES[storage_path] = UsersStorage(storage_path)

    return STORAGES[storage_path]


async def send_auth_menu(message: Message, text: str) -> None:
    # Отправка стартового меню
    await message.answer(text, reply_markup=get_start_keyboard())


async def send_main_menu(message: Message, text: str) -> None:
    # Отправка главного меню
    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext) -> None:
    # Сброс состояния по /start
    if message.from_user is None:
        return

    await state.clear()
    deauthorize_user(message.from_user.id)
    await send_auth_menu(
        message,
        "Привет! Это Telegram-бот UnitedLibra.\n"
        "Выберите действие: войти или зарегистрироваться.",
    )


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_TEXT)
async def cancel_command(message: Message, state: FSMContext) -> None:
    # Отмена текущей операции
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Активной операции нет.")
        return

    await state.clear()

    if message.from_user and is_authorized(message.from_user.id):
        await send_main_menu(message, "Операция отменена.")
        return

    await send_auth_menu(message, "Операция отменена.")


@router.message(StateFilter(None), F.text == LOGOUT_TEXT)
async def logout_command(message: Message, state: FSMContext) -> None:
    # Выход из аккаунта
    if message.from_user is None:
        return

    await state.clear()
    deauthorize_user(message.from_user.id)
    await send_auth_menu(message, "Вы вышли из аккаунта.")


@router.message(StateFilter(None), F.text == REGISTER_TEXT)
async def registration_entry(message: Message, state: FSMContext) -> None:
    # Старт регистрации
    if message.from_user and is_authorized(message.from_user.id):
        await send_main_menu(message, "Вы уже авторизованы.")
        return

    await state.clear()
    await state.set_state(RegistrationStates.waiting_full_name)
    await message.answer("Введите ФИО. Для отмены отправьте /cancel.")


@router.message(RegistrationStates.waiting_full_name)
async def registration_full_name_step(message: Message, state: FSMContext) -> None:
    # Получение ФИО
    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer("ФИО не должно быть пустым. Введите ФИО ещё раз.")
        return

    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationStates.waiting_login)
    await message.answer("Введите логин. Для отмены отправьте /cancel.")


@router.message(RegistrationStates.waiting_login)
async def registration_login_step(message: Message, state: FSMContext) -> None:
    # Получение логина
    login = (message.text or "").strip()
    if not is_valid_login(login):
        await message.answer(
            "Логин должен быть длиной от 3 до 32 символов и без пробелов.",
        )
        return

    await state.update_data(login=login)
    await state.set_state(RegistrationStates.waiting_password)
    await message.answer("Введите пароль. Для отмены отправьте /cancel.")


@router.message(RegistrationStates.waiting_password)
async def registration_password_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    # Регистрация пользователя
    if message.from_user is None:
        return

    password = (message.text or "").strip()
    if len(password) < 4:
        await message.answer("Пароль должен содержать минимум 4 символа.")
        return

    data = await state.get_data()
    storage = get_storage(settings)
    is_created, result = storage.register_user(
        full_name=data["full_name"],
        login=data["login"],
        password=password,
    )

    if not is_created and result == "user already exists":
        await state.clear()
        await send_auth_menu(message, "Такой логин уже зарегистрирован.")
        return

    if not is_created:
        await state.clear()
        await send_auth_menu(message, "Не удалось завершить регистрацию.")
        return

    authorize_user(message.from_user.id)
    await state.clear()
    await send_main_menu(message, "Регистрация завершена. Вход выполнен.")


@router.message(StateFilter(None), F.text == LOGIN_TEXT)
async def login_entry(message: Message, state: FSMContext) -> None:
    # Старт входа
    if message.from_user and is_authorized(message.from_user.id):
        await send_main_menu(message, "Вы уже авторизованы.")
        return

    await state.clear()
    await state.set_state(LoginStates.waiting_login)
    await message.answer("Введите логин. Для отмены отправьте /cancel.")


@router.message(LoginStates.waiting_login)
async def login_login_step(message: Message, state: FSMContext) -> None:
    # Получение логина для входа
    login = (message.text or "").strip()
    if not is_valid_login(login):
        await message.answer(
            "Логин должен быть длиной от 3 до 32 символов и без пробелов.",
        )
        return

    await state.update_data(login=login)
    await state.set_state(LoginStates.waiting_password)
    await message.answer("Введите пароль. Для отмены отправьте /cancel.")


@router.message(LoginStates.waiting_password)
async def login_password_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    # Проверка логина и пароля
    if message.from_user is None:
        return

    password = (message.text or "").strip()
    if not password:
        await message.answer("Пароль не должен быть пустым. Введите пароль ещё раз.")
        return

    data = await state.get_data()
    storage = get_storage(settings)
    is_verified, result = storage.verify_user(
        login=data["login"],
        password=password,
    )

    if not is_verified and result == "user not found":
        await state.clear()
        await send_auth_menu(message, "Пользователь с таким логином не найден.")
        return

    if not is_verified and result == "incorrect password":
        await state.clear()
        await send_auth_menu(message, "Неверный пароль. Начните вход заново.")
        return

    if not is_verified:
        await state.clear()
        await send_auth_menu(message, "Не удалось выполнить вход.")
        return

    authorize_user(message.from_user.id)
    await state.clear()
    await send_main_menu(message, "Вход выполнен!")


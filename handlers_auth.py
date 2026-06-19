import asyncio
import re
from typing import Any

from aiohttp import ClientError, ClientSession, ContentTypeError
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from config import Settings

router = Router(name="auth")

LOGIN_TEXT = "Войти"
REGISTER_TEXT = "Зарегистрироваться"
LOGOUT_TEXT = "Выйти"
CANCEL_TEXT = "Отмена"

AUTHORIZED_USERS: set[int] = set()
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationStates(StatesGroup):
    # Шаги регистрации
    waiting_name = State()
    waiting_email = State()
    waiting_password = State()
    waiting_code = State()


class LoginStates(StatesGroup):
    # Шаги входа
    waiting_email = State()
    waiting_password = State()
    waiting_code = State()


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


def build_auth_url(settings: Settings, path: str) -> str:
    # Сборка URL авторизации
    return f"{settings.AUTH_SERVICE_URL.rstrip('/')}{path}"


def is_valid_email(email: str) -> bool:
    # Проверка email
    return bool(EMAIL_PATTERN.fullmatch(email))


def extract_error(data: dict[str, Any], fallback: str) -> str:
    # Извлечение ошибки
    return str(data.get("error") or data.get("message") or fallback)


async def request_json(
    http_session: ClientSession,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int | None, dict[str, Any]]:
    # HTTP-запрос к бэкенду
    try:
        async with http_session.request(method=method, url=url, json=payload) as response:
            try:
                data = await response.json(content_type=None)
            except (ContentTypeError, ValueError):
                text = await response.text()
                data = {"error": text or "Некорректный ответ сервера"}

            if isinstance(data, dict):
                return response.status, data

            return response.status, {"data": data}
    except (asyncio.TimeoutError, ClientError):
        return None, {"error": "Сервис временно недоступен"}


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
    await state.set_state(RegistrationStates.waiting_name)
    await message.answer("Введите имя. Для отмены отправьте /cancel.")


@router.message(RegistrationStates.waiting_name)
async def registration_name_step(message: Message, state: FSMContext) -> None:
    # Получение имени
    name = (message.text or "").strip()
    if not name:
        await message.answer("Имя не должно быть пустым. Введите имя ещё раз.")
        return

    await state.update_data(name=name)
    await state.set_state(RegistrationStates.waiting_email)
    await message.answer("Введите email. Для отмены отправьте /cancel.")


@router.message(RegistrationStates.waiting_email)
async def registration_email_step(message: Message, state: FSMContext) -> None:
    # Получение email
    email = (message.text or "").strip()
    if not is_valid_email(email):
        await message.answer("Некорректный email. Введите email ещё раз.")
        return

    await state.update_data(email=email)
    await state.set_state(RegistrationStates.waiting_password)
    await message.answer("Введите пароль. Для отмены отправьте /cancel.")


@router.message(RegistrationStates.waiting_password)
async def registration_password_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Отправка данных регистрации
    password = (message.text or "").strip()
    if not password:
        await message.answer("Пароль не должен быть пустым. Введите пароль ещё раз.")
        return

    data = await state.get_data()
    await state.update_data(password=password)

    payload = {
        "name": data["name"],
        "email": data["email"],
        "password": password,
        "is_verifyCode": False,
    }

    _, response_data = await request_json(
        http_session,
        "POST",
        build_auth_url(settings, "/auth/register-user"),
        payload,
    )

    if response_data.get("error") == "user already exists":
        await state.clear()
        await send_auth_menu(message, "Такой email уже зарегистрирован.")
        return

    if response_data.get("status") == "ok":
        await state.set_state(RegistrationStates.waiting_code)
        await message.answer("Код отправлен на почту. Введите код подтверждения.")
        return

    await state.clear()
    await send_auth_menu(
        message,
        f"Не удалось начать регистрацию: {extract_error(response_data, 'Неизвестная ошибка')}.",
    )


@router.message(RegistrationStates.waiting_code)
async def registration_code_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Подтверждение регистрации
    if message.from_user is None:
        return

    code = (message.text or "").strip()
    if not code:
        await message.answer("Код не должен быть пустым. Введите код ещё раз.")
        return

    data = await state.get_data()
    payload = {
        "name": data["name"],
        "email": data["email"],
        "password": data["password"],
        "is_verifyCode": True,
        "code": code,
    }

    _, response_data = await request_json(
        http_session,
        "POST",
        build_auth_url(settings, "/auth/register-user"),
        payload,
    )

    if response_data.get("status") == "ok":
        authorize_user(message.from_user.id)
        await state.clear()
        await send_main_menu(message, "Регистрация завершена. Доступ к CRUD-меню открыт.")
        return

    await state.clear()
    await send_auth_menu(
        message,
        f"Не удалось завершить регистрацию: {extract_error(response_data, 'Неизвестная ошибка')}.",
    )


@router.message(StateFilter(None), F.text == LOGIN_TEXT)
async def login_entry(message: Message, state: FSMContext) -> None:
    # Старт входа
    if message.from_user and is_authorized(message.from_user.id):
        await send_main_menu(message, "Вы уже авторизованы.")
        return

    await state.clear()
    await state.set_state(LoginStates.waiting_email)
    await message.answer("Введите email. Для отмены отправьте /cancel.")


@router.message(LoginStates.waiting_email)
async def login_email_step(message: Message, state: FSMContext) -> None:
    # Получение email для входа
    email = (message.text or "").strip()
    if not is_valid_email(email):
        await message.answer("Некорректный email. Введите email ещё раз.")
        return

    await state.update_data(email=email)
    await state.set_state(LoginStates.waiting_password)
    await message.answer("Введите пароль. Для отмены отправьте /cancel.")


@router.message(LoginStates.waiting_password)
async def login_password_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Отправка данных входа
    password = (message.text or "").strip()
    if not password:
        await message.answer("Пароль не должен быть пустым. Введите пароль ещё раз.")
        return

    data = await state.get_data()
    await state.update_data(password=password)

    payload = {
        "email": data["email"],
        "password": password,
    }

    _, response_data = await request_json(
        http_session,
        "POST",
        build_auth_url(settings, "/auth/login-user"),
        payload,
    )

    if response_data.get("status") == "ok":
        await state.set_state(LoginStates.waiting_code)
        await message.answer("Код отправлен на почту. Введите код подтверждения.")
        return

    await state.clear()

    if response_data.get("error") == "user not found":
        await send_auth_menu(message, "Пользователь с таким email не найден.")
        return

    if response_data.get("error") == "incorrect password":
        await send_auth_menu(message, "Неверный пароль. Начните вход заново.")
        return

    await send_auth_menu(
        message,
        f"Не удалось выполнить вход: {extract_error(response_data, 'Неизвестная ошибка')}.",
    )


@router.message(LoginStates.waiting_code)
async def login_code_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Проверка кода входа
    if message.from_user is None:
        return

    code = (message.text or "").strip()
    if not code:
        await message.answer("Код не должен быть пустым. Введите код ещё раз.")
        return

    data = await state.get_data()
    payload = {
        "email": data["email"],
        "code": code,
    }

    _, response_data = await request_json(
        http_session,
        "POST",
        build_auth_url(settings, "/auth/verify-code"),
        payload,
    )

    if response_data.get("status") == "ok" or response_data.get("error") == "time is up":
        authorize_user(message.from_user.id)
        await state.clear()
        await send_main_menu(message, "Вход выполнен!")
        return

    if response_data.get("error") == "invalid code":
        await message.answer("Неверный код. Введите код ещё раз или отправьте /cancel.")
        return

    await state.clear()
    await send_auth_menu(
        message,
        f"Не удалось завершить вход: {extract_error(response_data, 'Неизвестная ошибка')}.",
    )

import asyncio
from datetime import datetime
from typing import Any

from aiohttp import ClientError, ClientSession, ContentTypeError
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Settings
from handlers_auth import get_main_menu_keyboard, get_start_keyboard, is_authorized

router = Router(name="crud")

ENTITY_BY_BUTTON = {
    "Книги": "books",
    "Авторы": "authors",
    "Категории": "categories",
    "Издатели": "publishers",
    "Издательства": "publishers",
}

ENTITY_CONFIG = {
    "authors": {
        "title": "Авторы",
        "emoji": "✍️",
        "list_endpoint": "/books/get-authors",
        "add_endpoint": "/books/add-authors",
        "delete_endpoint": "/books/delete-authors",
        "add_prompt": "Введите имя автора. Для отмены отправьте /cancel.",
        "delete_prompt": "Введите ID автора или несколько ID через запятую. Для отмены отправьте /cancel.",
        "add_success": "Автор добавлен.",
        "delete_success": "Автор(ы) удалён(ы).",
    },
    "categories": {
        "title": "Категории",
        "emoji": "🗂",
        "list_endpoint": "/books/get-categories",
        "add_endpoint": "/books/add-categories",
        "delete_endpoint": "/books/delete-categories",
        "add_prompt": "Введите название категории. Для отмены отправьте /cancel.",
        "delete_prompt": "Введите ID категории или несколько ID через запятую. Для отмены отправьте /cancel.",
        "add_success": "Категория добавлена.",
        "delete_success": "Категория(и) удалена(ы).",
    },
    "publishers": {
        "title": "Издатели",
        "emoji": "🏢",
        "list_endpoint": "/books/get-publishers",
        "add_endpoint": "/books/add-publishers",
        "delete_endpoint": "/books/delete-publishers",
        "add_prompt": "Введите имя издателя. Для отмены отправьте /cancel.",
        "delete_prompt": "Введите ID издателя или несколько ID через запятую. Для отмены отправьте /cancel.",
        "add_success": "Издатель добавлен.",
        "delete_success": "Издатель(и) удалён(ы).",
    },
    "books": {
        "title": "Книги",
        "emoji": "📚",
        "list_endpoint": "/books/get-book",
        "add_endpoint": "/books/add-book",
        "delete_endpoint": "/books/delete-book",
        "delete_prompt": "Введите ID книги или несколько ID через запятую. Для отмены отправьте /cancel.",
        "add_success": "Книга добавлена.",
        "delete_success": "Книга(и) удалена(ы).",
    },
}


class DictionaryStates(StatesGroup):
    # Шаги справочников
    waiting_name = State()
    waiting_delete_ids = State()


class BookStates(StatesGroup):
    # Шаги книги
    waiting_title = State()
    waiting_isbn = State()
    waiting_year = State()
    waiting_publisher_id = State()
    waiting_author_ids = State()
    waiting_category_ids = State()
    waiting_delete_ids = State()


def build_catalog_url(settings: Settings, path: str) -> str:
    # Сборка URL каталога
    return f"{settings.CATALOG_SERVICE_URL.rstrip('/')}{path}"


def build_entity_keyboard(entity_key: str) -> InlineKeyboardMarkup:
    # Клавиатура действий
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Просмотреть список",
                    callback_data=f"crud:list:{entity_key}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Добавить запись",
                    callback_data=f"crud:add:{entity_key}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Удалить запись",
                    callback_data=f"crud:delete:{entity_key}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Главное меню",
                    callback_data="crud:main",
                ),
            ],
        ],
    )


def extract_error(data: dict[str, Any], fallback: str) -> str:
    # Извлечение ошибки
    return str(data.get("error") or data.get("message") or fallback)


def parse_positive_int(raw_value: str) -> int:
    # Разбор числа
    value = int(raw_value.strip())
    if value <= 0:
        raise ValueError
    return value


def parse_ids(raw_value: str) -> list[int]:
    # Разбор списка ID
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    if not parts:
        raise ValueError

    ids = [parse_positive_int(part) for part in parts]
    return ids


def format_dictionary_item(item: dict[str, Any], emoji: str) -> str:
    # Форматирование справочника
    item_id = item.get("id", "-")
    name = item.get("name", "-")
    return f"🆔 ID: {item_id} | {emoji} Имя: {name}"


def format_book_item(item: dict[str, Any]) -> str:
    # Форматирование книги
    item_id = item.get("id", "-")
    title = item.get("title", "-")
    isbn = item.get("isbn", "-")
    year = item.get("year", "-")
    publisher_id = item.get("publisher_id", item.get("description", "-"))

    return (
        f"🆔 ID: {item_id} | "
        f"📘 Название: {title} | "
        f"🔢 ISBN: {isbn} | "
        f"📅 Год: {year} | "
        f"🏢 Издатель ID: {publisher_id}"
    )


def format_entity_list(entity_key: str, items: list[dict[str, Any]]) -> str:
    # Сборка текста списка
    if not items:
        return f"Список раздела «{ENTITY_CONFIG[entity_key]['title']}» пуст."

    lines = [f"Раздел «{ENTITY_CONFIG[entity_key]['title']}»:"] 

    for item in items:
        if entity_key == "books":
            lines.append(format_book_item(item))
            continue

        lines.append(format_dictionary_item(item, ENTITY_CONFIG[entity_key]["emoji"]))

    return "\n".join(lines)


def split_text(text: str, limit: int = 3800) -> list[str]:
    # Разделение длинного текста
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current_chunk = ""

    for line in text.splitlines():
        candidate = f"{current_chunk}\n{line}".strip() if current_chunk else line
        if len(candidate) <= limit:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)
        current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def request_json(
    http_session: ClientSession,
    method: str,
    url: str,
    payload: Any = None,
) -> tuple[int | None, dict[str, Any]]:
    # HTTP-запрос к каталогу
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


async def ensure_crud_access(message: Message) -> bool:
    # Проверка доступа к CRUD
    if message.from_user and is_authorized(message.from_user.id):
        return True

    await message.answer(
        "Сначала выполните вход через /start.",
        reply_markup=get_start_keyboard(),
    )
    return False


async def ensure_callback_access(callback: CallbackQuery) -> bool:
    # Проверка доступа для callback
    if callback.from_user and is_authorized(callback.from_user.id):
        return True

    await callback.answer("Сначала выполните вход через /start.", show_alert=True)
    if callback.message:
        await callback.message.answer(
            "Доступ к CRUD-меню закрыт до входа.",
            reply_markup=get_start_keyboard(),
        )
    return False


async def send_entity_menu(message: Message, entity_key: str, text: str | None = None) -> None:
    # Отправка меню раздела
    await message.answer(
        text or f"Раздел «{ENTITY_CONFIG[entity_key]['title']}». Выберите действие.",
        reply_markup=build_entity_keyboard(entity_key),
    )


async def send_list_result(message: Message, entity_key: str, text: str) -> None:
    # Отправка результата списка
    parts = split_text(text)

    for index, part in enumerate(parts):
        markup = build_entity_keyboard(entity_key) if index == len(parts) - 1 else None
        await message.answer(part, reply_markup=markup)


async def create_book(
    http_session: ClientSession,
    settings: Settings,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # Создание книги
    _, response_data = await request_json(
        http_session,
        "POST",
        build_catalog_url(settings, ENTITY_CONFIG["books"]["add_endpoint"]),
        payload,
    )

    if response_data.get("status") == "ok":
        return response_data

    compatibility_payload = dict(payload)
    compatibility_payload["description"] = str(payload["publisher_id"])

    # Повторная отправка для текущего бэкенда
    _, compatibility_data = await request_json(
        http_session,
        "POST",
        build_catalog_url(settings, ENTITY_CONFIG["books"]["add_endpoint"]),
        compatibility_payload,
    )

    if compatibility_data.get("status") == "ok":
        return compatibility_data

    return compatibility_data or response_data


@router.message(StateFilter(None), Command("menu"))
async def main_menu_command(message: Message) -> None:
    # Показ главного меню
    if not await ensure_crud_access(message):
        return

    await message.answer(
        "Главное меню. Выберите таблицу.",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(StateFilter(None), F.text.in_(tuple(ENTITY_BY_BUTTON.keys())))
async def entity_menu_entry(message: Message) -> None:
    # Вход в раздел таблицы
    if not await ensure_crud_access(message):
        return

    entity_key = ENTITY_BY_BUTTON[message.text]
    await send_entity_menu(message, entity_key)


@router.callback_query(StateFilter(None), F.data == "crud:main")
async def main_menu_callback(callback: CallbackQuery) -> None:
    # Возврат в главное меню
    if not await ensure_callback_access(callback):
        return

    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Главное меню. Выберите таблицу.",
            reply_markup=get_main_menu_keyboard(),
        )


@router.callback_query(StateFilter(None), F.data.startswith("crud:list:"))
async def list_records_callback(
    callback: CallbackQuery,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Получение списка записей
    if not await ensure_callback_access(callback):
        return

    entity_key = callback.data.rsplit(":", maxsplit=1)[-1]
    _, response_data = await request_json(
        http_session,
        "GET",
        build_catalog_url(settings, ENTITY_CONFIG[entity_key]["list_endpoint"]),
    )

    if callback.message is None:
        await callback.answer()
        return

    if response_data.get("status") != "ok":
        await callback.message.answer(
            f"Не удалось получить список: {extract_error(response_data, 'Неизвестная ошибка')}.",
            reply_markup=build_entity_keyboard(entity_key),
        )
        await callback.answer()
        return

    items = response_data.get("data")
    if not isinstance(items, list):
        items = []

    text = format_entity_list(entity_key, items)
    await send_list_result(callback.message, entity_key, text)
    await callback.answer()


@router.callback_query(StateFilter(None), F.data.startswith("crud:add:"))
async def add_record_entry(callback: CallbackQuery, state: FSMContext) -> None:
    # Выбор добавления записи
    if not await ensure_callback_access(callback):
        return

    entity_key = callback.data.rsplit(":", maxsplit=1)[-1]
    await state.clear()
    await state.update_data(entity=entity_key)

    if callback.message is None:
        await callback.answer()
        return

    if entity_key == "books":
        await state.set_state(BookStates.waiting_title)
        await callback.message.answer("Введите название книги. Для отмены отправьте /cancel.")
        await callback.answer()
        return

    await state.set_state(DictionaryStates.waiting_name)
    await callback.message.answer(ENTITY_CONFIG[entity_key]["add_prompt"])
    await callback.answer()


@router.callback_query(StateFilter(None), F.data.startswith("crud:delete:"))
async def delete_record_entry(callback: CallbackQuery, state: FSMContext) -> None:
    # Выбор удаления записи
    if not await ensure_callback_access(callback):
        return

    entity_key = callback.data.rsplit(":", maxsplit=1)[-1]
    await state.clear()
    await state.update_data(entity=entity_key)

    if callback.message is None:
        await callback.answer()
        return

    if entity_key == "books":
        await state.set_state(BookStates.waiting_delete_ids)
    else:
        await state.set_state(DictionaryStates.waiting_delete_ids)

    await callback.message.answer(ENTITY_CONFIG[entity_key]["delete_prompt"])
    await callback.answer()


@router.message(DictionaryStates.waiting_name)
async def dictionary_name_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Добавление записи в справочник
    if not await ensure_crud_access(message):
        return

    value = (message.text or "").strip()
    if not value:
        await message.answer("Текст не должен быть пустым. Введите значение ещё раз.")
        return

    data = await state.get_data()
    entity_key = data.get("entity")
    if entity_key not in ENTITY_CONFIG:
        await state.clear()
        await message.answer("Состояние операции потеряно.", reply_markup=get_main_menu_keyboard())
        return

    payload = {"name": value}
    _, response_data = await request_json(
        http_session,
        "POST",
        build_catalog_url(settings, ENTITY_CONFIG[entity_key]["add_endpoint"]),
        payload,
    )

    await state.clear()

    if response_data.get("status") == "ok":
        await message.answer(
            ENTITY_CONFIG[entity_key]["add_success"],
            reply_markup=build_entity_keyboard(entity_key),
        )
        return

    await message.answer(
        f"Не удалось добавить запись: {extract_error(response_data, 'Неизвестная ошибка')}.",
        reply_markup=build_entity_keyboard(entity_key),
    )


@router.message(DictionaryStates.waiting_delete_ids)
@router.message(BookStates.waiting_delete_ids)
async def delete_ids_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Удаление записей по ID
    if not await ensure_crud_access(message):
        return

    try:
        ids = parse_ids(message.text or "")
    except (ValueError, TypeError):
        await message.answer("Некорректный список ID. Введите числа через запятую.")
        return

    data = await state.get_data()
    entity_key = data.get("entity")
    if entity_key not in ENTITY_CONFIG:
        await state.clear()
        await message.answer("Состояние операции потеряно.", reply_markup=get_main_menu_keyboard())
        return

    payload = [{"id": item_id} for item_id in ids]
    _, response_data = await request_json(
        http_session,
        "POST",
        build_catalog_url(settings, ENTITY_CONFIG[entity_key]["delete_endpoint"]),
        payload,
    )

    await state.clear()

    if response_data.get("status") == "ok":
        await message.answer(
            ENTITY_CONFIG[entity_key]["delete_success"],
            reply_markup=build_entity_keyboard(entity_key),
        )
        return

    await message.answer(
        f"Не удалось удалить запись: {extract_error(response_data, 'Неизвестная ошибка')}.",
        reply_markup=build_entity_keyboard(entity_key),
    )


@router.message(BookStates.waiting_title)
async def book_title_step(message: Message, state: FSMContext) -> None:
    # Получение названия книги
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым. Введите название ещё раз.")
        return

    await state.update_data(title=title)
    await state.set_state(BookStates.waiting_isbn)
    await message.answer("Введите ISBN. Для отмены отправьте /cancel.")


@router.message(BookStates.waiting_isbn)
async def book_isbn_step(message: Message, state: FSMContext) -> None:
    # Получение ISBN
    isbn = (message.text or "").strip()
    if not isbn:
        await message.answer("ISBN не должен быть пустым. Введите ISBN ещё раз.")
        return

    await state.update_data(isbn=isbn)
    await state.set_state(BookStates.waiting_year)
    await message.answer("Введите год издания. Для отмены отправьте /cancel.")


@router.message(BookStates.waiting_year)
async def book_year_step(message: Message, state: FSMContext) -> None:
    # Получение года
    try:
        year = int((message.text or "").strip())
    except ValueError:
        await message.answer("Год должен быть числом. Введите год ещё раз.")
        return

    current_year = datetime.now().year + 1
    if year < 1000 or year > current_year:
        await message.answer("Введите корректный год издания.")
        return

    await state.update_data(year=year)
    await state.set_state(BookStates.waiting_publisher_id)
    await message.answer("Введите ID издателя. Для отмены отправьте /cancel.")


@router.message(BookStates.waiting_publisher_id)
async def book_publisher_step(message: Message, state: FSMContext) -> None:
    # Получение ID издателя
    try:
        publisher_id = parse_positive_int(message.text or "")
    except (ValueError, TypeError):
        await message.answer("ID издателя должен быть положительным числом.")
        return

    await state.update_data(publisher_id=publisher_id)
    await state.set_state(BookStates.waiting_author_ids)
    await message.answer("Введите ID авторов через запятую. Для отмены отправьте /cancel.")


@router.message(BookStates.waiting_author_ids)
async def book_authors_step(message: Message, state: FSMContext) -> None:
    # Получение ID авторов
    try:
        author_ids = parse_ids(message.text or "")
    except (ValueError, TypeError):
        await message.answer("Введите корректные ID авторов через запятую.")
        return

    await state.update_data(author_ids=author_ids)
    await state.set_state(BookStates.waiting_category_ids)
    await message.answer("Введите ID категорий через запятую. Для отмены отправьте /cancel.")


@router.message(BookStates.waiting_category_ids)
async def book_categories_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    http_session: ClientSession,
) -> None:
    # Получение ID категорий и отправка книги
    if not await ensure_crud_access(message):
        return

    try:
        category_ids = parse_ids(message.text or "")
    except (ValueError, TypeError):
        await message.answer("Введите корректные ID категорий через запятую.")
        return

    data = await state.get_data()
    payload = {
        "title": data["title"],
        "isbn": data["isbn"],
        "year": data["year"],
        "publisher_id": data["publisher_id"],
        "author_ids": data["author_ids"],
        "category_ids": category_ids,
    }

    response_data = await create_book(http_session, settings, payload)
    await state.clear()

    if response_data.get("status") == "ok":
        await message.answer(
            ENTITY_CONFIG["books"]["add_success"],
            reply_markup=build_entity_keyboard("books"),
        )
        return

    await message.answer(
        f"Не удалось добавить книгу: {extract_error(response_data, 'Неизвестная ошибка')}.",
        reply_markup=build_entity_keyboard("books"),
    )


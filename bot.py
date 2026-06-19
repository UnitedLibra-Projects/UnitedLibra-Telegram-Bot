import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import get_settings
from handlers_auth import router as auth_router
from handlers_crud import router as crud_router


async def main() -> None:
    # Настройка логов
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    settings = get_settings()
    bot = Bot(token=settings.BOT_TOKEN)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(auth_router)
    dispatcher.include_router(crud_router)

    timeout = aiohttp.ClientTimeout(total=15)

    # Общая HTTP-сессия
    async with aiohttp.ClientSession(timeout=timeout) as http_session:
        try:
            await dispatcher.start_polling(
                bot,
                settings=settings,
                http_session=http_session,
            )
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

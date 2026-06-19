from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Параметры бота
    BOT_TOKEN: str
    CATALOG_SERVICE_URL: str
    USERS_STORAGE_PATH: str = "users.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    # Кэширование настроек
    return Settings()

import hashlib
import hmac
import json
import secrets
from pathlib import Path


class UsersStorage:
    # Хранилище пользователей
    def __init__(self, storage_path: str) -> None:
        self.storage_path = Path(storage_path)

    def register_user(self, full_name: str, login: str, password: str) -> tuple[bool, str]:
        # Регистрация пользователя
        data = self._load_data()
        normalized_login = self._normalize_login(login)

        if normalized_login in data["users"]:
            return False, "user already exists"

        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)

        data["users"][normalized_login] = {
            "full_name": full_name,
            "login": login,
            "password_salt": salt,
            "password_hash": password_hash,
        }

        self._save_data(data)
        return True, "ok"

    def verify_user(self, login: str, password: str) -> tuple[bool, str]:
        # Проверка логина и пароля
        data = self._load_data()
        normalized_login = self._normalize_login(login)
        user = data["users"].get(normalized_login)

        if user is None:
            return False, "user not found"

        expected_hash = self._hash_password(password, user["password_salt"])
        if not hmac.compare_digest(expected_hash, user["password_hash"]):
            return False, "incorrect password"

        return True, "ok"

    def _load_data(self) -> dict[str, dict]:
        # Чтение файла пользователей
        if not self.storage_path.exists():
            return {"users": {}}

        try:
            raw_data = self.storage_path.read_text(encoding="utf-8")
            parsed_data = json.loads(raw_data)
        except (OSError, json.JSONDecodeError):
            return {"users": {}}

        if not isinstance(parsed_data, dict):
            return {"users": {}}

        users = parsed_data.get("users")
        if not isinstance(users, dict):
            return {"users": {}}

        return {"users": users}

    def _save_data(self, data: dict[str, dict]) -> None:
        # Сохранение файла пользователей
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_login(login: str) -> str:
        # Нормализация логина
        return login.strip().lower()

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        # Хеширование пароля
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return password_hash.hex()


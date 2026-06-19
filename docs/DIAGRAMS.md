# Диаграммы проекта

## 1. Блок-схема общей работы системы

```mermaid
flowchart TD
    A["Пользователь открывает Telegram-бота"] --> B["Команда /start"]
    B --> C["Стартовое меню"]
    C --> D["Регистрация"]
    C --> E["Вход"]
    D --> F["Локальное хранилище users.json"]
    E --> F
    F --> G{"Авторизация успешна?"}
    G -- "Нет" --> C
    G -- "Да" --> H["Главное меню"]
    H --> I["Авторы"]
    H --> J["Категории"]
    H --> K["Издатели"]
    H --> L["Книги"]
    I --> M["Catalog Backend"]
    J --> M
    K --> M
    L --> M
    M --> N["PostgreSQL"]
```

## 2. Блок-схема регистрации и входа

```mermaid
flowchart TD
    A["/start"] --> B["Показ кнопок Войти и Зарегистрироваться"]
    B --> C{"Выбор пользователя"}
    C -- "Зарегистрироваться" --> D["Ввод ФИО"]
    D --> E["Ввод логина"]
    E --> F["Ввод пароля"]
    F --> G["Создание пользователя в users.json"]
    G --> H["Открытие главного меню"]
    C -- "Войти" --> I["Ввод логина"]
    I --> J["Ввод пароля"]
    J --> K{"Логин и пароль верны?"}
    K -- "Нет" --> B
    K -- "Да" --> H
```

## 3. Блок-схема CRUD-операций

```mermaid
flowchart TD
    A["Пользователь авторизован"] --> B["Выбор раздела"]
    B --> C["Авторы"]
    B --> D["Категории"]
    B --> E["Издатели"]
    B --> F["Книги"]
    C --> G["Просмотреть / Добавить / Удалить"]
    D --> G
    E --> G
    F --> H["Просмотреть / Добавить / Удалить книгу"]
    G --> I["HTTP запрос в Catalog Backend"]
    H --> I
    I --> J["Обработка в контроллерах backend"]
    J --> K["Запросы в PostgreSQL"]
    K --> L["JSON-ответ"]
    L --> M["Сообщение пользователю в Telegram"]
```

## 4. UML-диаграмма классов

```mermaid
classDiagram
    class Settings {
        +BOT_TOKEN: str
        +CATALOG_SERVICE_URL: str
        +USERS_STORAGE_PATH: str
    }

    class UsersStorage {
        +register_user(full_name, login, password)
        +verify_user(login, password)
        -load_data()
        -save_data()
        -hash_password()
    }

    class RegistrationStates {
        +waiting_full_name
        +waiting_login
        +waiting_password
    }

    class LoginStates {
        +waiting_login
        +waiting_password
    }

    class DictionaryStates {
        +waiting_name
        +waiting_delete_ids
    }

    class BookStates {
        +waiting_title
        +waiting_isbn
        +waiting_year
        +waiting_publisher_id
        +waiting_author_ids
        +waiting_category_ids
        +waiting_delete_ids
    }

    class AuthHandlers {
        +start_command()
        +registration_entry()
        +login_entry()
        +logout_command()
        +cancel_command()
    }

    class CrudHandlers {
        +entity_menu_entry()
        +list_records_callback()
        +add_record_entry()
        +delete_record_entry()
        +dictionary_name_step()
        +delete_ids_step()
        +book_title_step()
        +book_categories_step()
    }

    class CatalogBackend {
        +GET get-authors
        +GET get-categories
        +GET get-publishers
        +GET get-book
        +POST add-*
        +POST delete-*
    }

    class PostgreSQL {
        +authors
        +categories
        +publisher
        +books
        +bookauthors
        +bookcategories
    }

    AuthHandlers --> Settings
    AuthHandlers --> UsersStorage
    CrudHandlers --> Settings
    CrudHandlers --> CatalogBackend
    CatalogBackend --> PostgreSQL
    AuthHandlers --> RegistrationStates
    AuthHandlers --> LoginStates
    CrudHandlers --> DictionaryStates
    CrudHandlers --> BookStates
```

## 5. ER-диаграмма базы данных

```mermaid
erDiagram
    AUTHORS {
        int id PK
        text name
    }

    CATEGORIES {
        int id PK
        text name
    }

    PUBLISHER {
        int id PK
        text name
    }

    BOOKS {
        int id PK
        text title
        text description
        text isbn
        int year
        int publisher_id FK
        timestamp created_at
    }

    BOOKAUTHORS {
        int book_id FK
        int author_id FK
    }

    BOOKCATEGORIES {
        int book_id FK
        int category_id FK
    }

    LOCATIONS {
        int id PK
        text hall
        text shelf
    }

    BOOKCOPY {
        int id PK
        int book_id FK
        text picture_adress
        text status
        int location_id FK
        int count
        text state_description
    }

    BOOKCOPYPUBLISHERS {
        int book_copy_id FK
        int publisher_id FK
    }

    USERS {
        int id PK
        text name
        text email
        text password
    }

    PUBLISHER ||--o{ BOOKS : "publisher_id"
    BOOKS ||--o{ BOOKAUTHORS : "book_id"
    AUTHORS ||--o{ BOOKAUTHORS : "author_id"
    BOOKS ||--o{ BOOKCATEGORIES : "book_id"
    CATEGORIES ||--o{ BOOKCATEGORIES : "category_id"
    BOOKS ||--o{ BOOKCOPY : "book_id"
    LOCATIONS ||--o{ BOOKCOPY : "location_id"
    BOOKCOPY ||--o{ BOOKCOPYPUBLISHERS : "book_copy_id"
    PUBLISHER ||--o{ BOOKCOPYPUBLISHERS : "publisher_id"
```

## 6. Краткое пояснение

- Бот состоит из двух основных частей: авторизация и CRUD.
- Авторизация в текущей версии локальная и использует `users.json`.
- Работа со справочниками и книгами идет через отдельный backend каталога.
- Backend каталога использует PostgreSQL.
- Диаграммы отражают текущую рабочую структуру проекта, которая используется в репозитории.


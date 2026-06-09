import telebot
import requests
from telebot import types
from telebot import apihelper

BOT_TOKEN = "8993552703:AAGwFJ4k3JYMk-mar3UTmBXn55ctqvmK_AQ"

# Создаем бота с учетом прокси
bot = telebot.TeleBot(BOT_TOKEN)

# Базовый URL бэкенда регистрации (из твоей документации)
BASE_URL = "http://127.0.0.1:8000"

# Временная память бота для хранения данных формы регистрации
user_data = {}

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    """Приветствие и создание кнопки Регистрация"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_reg = types.KeyboardButton("📝 Регистрация")
    markup.add(btn_reg)
    
    bot.send_message(
        message.chat.id, 
        "Привет! Это бот библиотеки UnitedLibra.\nНажми на кнопку ниже, чтобы пройти регистрацию.", 
        reply_markup=markup
    )

# Обработчик нажатия на кнопку "Регистрация"
@bot.message_handler(func=lambda message: message.text == "📝 Регистрация")
def start_registration(message):
    """Шаг 1: Запрашиваем Имя"""
    chat_id = message.chat.id
    user_data[chat_id] = {} # Инициализируем пустой словарь для юзера
    
    msg = bot.send_message(chat_id, "Введите ваше Имя и Фамилию:")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    """Шаг 2: Сохраняем имя и запрашиваем Email"""
    chat_id = message.chat.id
    user_data[chat_id]['name'] = message.text
    
    msg = bot.send_message(chat_id, "Отлично! Теперь введите ваш Email (почту):")
    bot.register_next_step_handler(msg, process_email_step)

def process_email_step(message):
    """Шаг 3: Сохраняем email и запрашиваем Пароль"""
    chat_id = message.chat.id
    user_data[chat_id]['email'] = message.text
    
    msg = bot.send_message(chat_id, "Придумайте и введите пароль:")
    bot.register_next_step_handler(msg, process_password_step)

def process_password_step(message):
    """Шаг 4: Отправляем запрос на бэк для высылки кода на почту"""
    chat_id = message.chat.id
    user_data[chat_id]['password'] = message.text
    
    bot.send_message(chat_id, "Отправляю данные на сервер для проверки...")
    
    # Структура JSON строго по вашей доке API (is_verifyCode: false)
    payload = {
        "name": user_data[chat_id]['name'],
        "email": user_data[chat_id]['email'],
        "password": user_data[chat_id]['password'],
        "is_verifyCode": False
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register-user", json=payload)
        res_data = response.json()
        
        # Проверяем ответ бэкенда регистрации
        if res_data.get("status") == "ok":
            msg = bot.send_message(chat_id, "Код подтверждения отправлен на вашу почту. Введите 6-значный код:")
            bot.register_next_step_handler(msg, process_verification_code)
        elif "error" in res_data:
            bot.send_message(chat_id, f"Ошибка бэкенда: {res_data['error']}. Попробуйте регистрацию заново.")
            
    except Exception as e:
        bot.send_message(chat_id, "❌ Не удалось связаться с сервером User-Registration. Проверь, запущен ли бэкенд.")
        print(f"Ошибка соединения: {e}")

def process_verification_code(message):
    """Шаг 5: Проверка кода и финальное создание аккаунта"""
    chat_id = message.chat.id
    code = message.text
    
    # Сначала проверяем код через эндпоинт верификации кодов
    verify_payload = {
        "email": user_data[chat_id]['email'],
        "code": code
    }
    
    try:
        verify_res = requests.post(f"{BASE_URL}/auth/verify-code", json=verify_payload)
        verify_data = verify_res.json()
        
        if verify_data.get("status") == "ok":
            # Если код верный, шлем повторный запрос на регистрацию, но уже с True
            final_payload = {
                "name": user_data[chat_id]['name'],
                "email": user_data[chat_id]['email'],
                "password": user_data[chat_id]['password'],
                "is_verifyCode": True
            }
            
            final_res = requests.post(f"{BASE_URL}/auth/register-user", json=final_payload)
            
            if final_res.json().get("status") == "ok":
                show_database_menu(message)
            else:
                bot.send_message(chat_id, "Ошибка при финальном сохранении пользователя.")
        else:
            # Тут отработает ваша дока (ошибки "time is up" или "invalid code")
            bot.send_message(chat_id, f"Ошибка: {verify_data.get('error')}. Начните регистрацию заново.")
            
    except Exception as e:
        bot.send_message(chat_id, "Ошибка при обработке кода верификации.")
        print(e)

def show_database_menu(message):
    """Концепт: Успешный вход, открываем меню таблиц (Шаги 2, 3, 4 от тимлида)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📚 Книги", "✍️ Авторы")
    markup.row("🏢 Издательства", "🗂 Категории")
    
    bot.send_message(
        message.chat.id, 
        "🎉 Регистрация успешна! Вам открыт доступ к редактированию базы данных.\nВыберите таблицу:", 
        reply_markup=markup
    )

if __name__ == '__main__':
    print("Робот запущен. Нажмите Ctrl+C в терминале для остановки.")
    bot.polling(none_stop=True)
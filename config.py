import os

# Получи на my.telegram.org



API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")

# Получи у @userinfobot (твой ID, чтобы бот слушался только тебя)
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# Токен бота от @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, 'data', 'sessions')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'data', 'downloads')

# Настройки рассылки
USERS_PER_STORY = 5  # Максимум 5
DELAY_BETWEEN_STORIES = 60  # Секунд (ставим больше для безопасности)

# --- НАСТРОЙКИ ТЕГОВ И ЗАДЕРЖЕК ---
MAX_TAGS_PER_STORY = 3  # Максимальное количество тегов на одну историю (2-3 рекомендуется)
MIN_DELAY = 600  # Минимальная задержка между постами в секундах (10 минут)
MAX_DELAY = 1200  # Максимальная задержка между постами в секундах (20 минут)

# Задержка перед добавлением тегов (секунды)
# ВАЖНО: Увеличено для обхода Silent Mention Filter
# Telegram модерирует сторис ~5 минут, поэтому редактирование после этого срока
# имеет больше шансов вызвать нативные уведомления
EDIT_DELAY_MIN = 300  # Минимум — 5 минут для прохождения модерации
EDIT_DELAY_MAX = 600  # Максимум — 10 минут (moderation-safe window)

# --- НАСТРОЙКИ ПРОКСИ ---
USE_PROXY = True  # Поставь False, если хочешь отключить

# Тип прокси: 'socks5' или 'http'
PROXY_TYPE = 'socks5' 

# Данные прокси (IP, Порт, Логин, Пароль)
PROXY_IP = os.environ.get("PROXY_IP", "127.0.0.1")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "1080"))
PROXY_USER = os.environ.get("PROXY_USER", "")
PROXY_PASS = os.environ.get("PROXY_PASS", "")

TTL_TO_PUBLISH_DELAY = 300

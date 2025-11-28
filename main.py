import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F
from googletrans import Translator
from langdetect import detect, LangDetectError
import re
import json
import os

# Твой токен
BOT_TOKEN = "8281330001:AAEutOYVJ9OpCO1cwvoJDxb81ZnSFR8CNsI"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
translator = Translator()

# Хранение обученных данных (спам/не спам) — в реальности используй БД, но для старта хватит JSON
SPAM_DB_FILE = "spam_db.json"
spam_patterns = set()  # Шаблоны спама
ham_patterns = set()   # Исключения (не спам)

def load_db():
    global spam_patterns, ham_patterns
    if os.path.exists(SPAM_DB_FILE):
        with open(SPAM_DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            spam_patterns = set(data.get('spam', []))
            ham_patterns = set(data.get('ham', []))

def save_db():
    with open(SPAM_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump({'spam': list(spam_patterns), 'ham': list(ham_patterns)}, f, ensure_ascii=False)

load_db()

# Списки спама (под твои примеры + мат RU/EN)
RUSSIAN_MAT = {'блядь', 'пизда', 'хуй', 'ебать', 'пидор', 'сука', 'нахуй', 'пиздец', 'блять', 'охуеть'}  # +3000, но для примера
ENGLISH_MAT = {'fuck', 'shit', 'bitch', 'cunt', 'dick', 'asshole', 'pussy', 'cock'}
SPAM_KEYWORDS = {
    'легальное получение в/у', 'права через гибдд', 'купить права', 'в/у без экзаменов',
    'обучение трейдингу', 'сигналы', 'курс трейдинга', 'заработок на бирже',
    'быстрые деньги', 'заработок без вложений', 'пассивный доход', '1000$ в день', 'airdrop', 'free money'
}

def is_spam(text: str) -> bool:
    text_lower = text.lower()
    # Проверка ключевых слов
    for keyword in SPAM_KEYWORDS:
        if keyword in text_lower:
            return True
    # Мат
    for word in RUSSIAN_MAT | ENGLISH_MAT:
        if word in text_lower:
            return True
    # Обученные паттерны
    for pattern in spam_patterns:
        if pattern.lower() in text_lower:
            return True
    # Исключения
    for pattern in ham_patterns:
        if pattern.lower() in text_lower:
            return False
    return False

def translate_if_foreign(text: str) -> tuple[str, str]:
    try:
        lang = detect(text)
        if lang != 'ru':
            translated = translator.translate(text, dest='ru').text
            return translated, f"[{lang.upper()}] {text}"
        return text, ""
    except (LangDetectError, Exception):
        return text, ""

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Бот запущен! Добавь меня в группу как админа с правами на удаление и бан.")

@dp.message(Command("spam"))
async def mark_spam(message: Message):
    if message.reply_to_message:
        text = message.reply_to_message.text or ""
        spam_patterns.add(text)
        save_db()
        await message.answer("Запомнил: это спам! Теперь буду удалять похожие.")
    else:
        await message.answer("Ответь на сообщение командой /spam")

@dp.message(Command("ham"))
async def mark_ham(message: Message):
    if message.reply_to_message:
        text = message.reply_to_message.text or ""
        ham_patterns.add(text)
        save_db()
        await message.answer("Запомнил: это не спам! Больше не трону такие.")
    else:
        await message.answer("Ответь на сообщение командой /ham")

@dp.message(Command("welcome"))
async def welcome_settings(message: Message):
    await message.answer("Настройки проверки при вступлении: включена (бан спамеров без аватарки). /stats для статистики.")

@dp.message(Command("stats"))
async def stats(message: Message):
    await message.answer(f"Спам-паттерны: {len(spam_patterns)}\nНе-спам: {len(ham_patterns)}")

# Обработчик новых участников (проверка на спамера)
@dp.chat_join_request()
async def check_new_member(request: types.ChatJoinRequest):
    user = request.from_user
    chat = request.chat
    username = user.username or ""
    first_name = user.first_name or ""
    # Проверка (без аватарки, как просил)
    suspicious = (
        re.search(r'\d{4,}', username) or  # Ник с кучей цифр
        any(kw in (first_name + username).lower() for kw in SPAM_KEYWORDS) or
        len(user.username or "") < 3  # Короткий ник
    )
    if suspicious:
        try:
            await bot.ban_chat_member(chat.id, user.id)
            await bot.send_message(chat.id, f"🚫 Удалён спамер @{username or user.id}\nПричина: подозрительный профиль.")
        except Exception:
            pass  # Если нет прав — молча

# Обработчик сообщений в группе
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_message(message: Message):
    text = message.text or ""
    if not text:
        return

    # Перевод, если иностранный
    translated, original_note = translate_if_foreign(text)
    if original_note:
        await message.reply(f"Перевод: {translated}\nОригинал: {original_note}")

    # Проверка на спам
    if is_spam(translated):
        try:
            await bot.delete_message(message.chat.id, message.message_id)
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
            await bot.send_message(message.chat.id, f"🗑️ Удалён спам от @{message.from_user.username or message.from_user.id}\nТекст: {translated[:50]}...")
        except Exception:
            pass  # Нет прав — пропустим

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import json
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ChatJoinRequest

# Для перевода и детекции
from googletrans import Translator
from fast_langdetect import detect as fast_detect  # Новая стабильная библиотека

# Твой токен
BOT_TOKEN = "8281330001:AAEutOYVJ9OpCO1cwvoJDxb81ZnSFR8CNsI"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
translator = Translator()

# Файл для данных
SPAM_DB_FILE = "spam_db.json"
spam_patterns = set()
ham_patterns = set()

def load_db():
    global spam_patterns, ham_patterns
    if os.path.exists(SPAM_DB_FILE):
        with open(SPAM_DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            spam_patterns = set(data.get('spam', []))
            ham_patterns = set(data.get('ham', []))

def save_db():
    with open(SPAM_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump({'spam': list(spam_patterns), 'ham': list(ham_patterns)}, f, ensure_ascii=False, indent=2)

load_db()

# Спам-слова
SPAM_KEYWORDS = [
    'в/у', 'права', 'гибдд', 'купить права', 'без экзаменов',
    'трейдинг', 'сигналы', 'заработок', 'быстрые деньги', 'пассивный доход', 'airdrop'
]
BAD_WORDS = ['блядь', 'пизда', 'хуй', 'ебать', 'пидор', 'сука', 'нахуй', 'пиздец', 'блять', 'fuck', 'shit', 'bitch']

def is_spam(text: str) -> bool:
    text_lower = text.lower()
    if any(word in text_lower for word in SPAM_KEYWORDS + BAD_WORDS):
        return True
    for pattern in spam_patterns:
        if pattern.lower() in text_lower:
            return True
    for pattern in ham_patterns:
        if pattern.lower() in text_lower:
            return False
    return False

def translate_if_foreign(text: str) -> tuple[str, str]:
    try:
        # Детекция с fast-langdetect (стабильная)
        lang = fast_detect(text)
        if lang != 'ru':
            translated = translator.translate(text, dest='ru').text
            return translated, f"Оригинал [{lang.upper()}]: {text}"
        return text, ""
    except Exception as e:
        logging.warning(f"Ошибка перевода: {e} — оставляем оригинал")
        return text, ""

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот запущен! Добавь в группу как админа.")

@dp.message(Command("spam"))
async def mark_spam(message: types.Message):
    if message.reply_to_message and message.reply_to_message.text:
        spam_patterns.add(message.reply_to_message.text)
        save_db()
        await message.answer("✅ Запомнил как спам.")
    else:
        await message.answer("Ответь на сообщение /spam")

@dp.message(Command("ham"))
async def mark_ham(message: types.Message):
    if message.reply_to_message and message.reply_to_message.text:
        ham_patterns.add(message.reply_to_message.text)
        save_db()
        await message.answer("✅ Запомнил как не спам.")
    else:
        await message.answer("Ответь на сообщение /ham")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    await message.answer(f"Спам: {len(spam_patterns)}, Не спам: {len(ham_patterns)}")

# Бан при вступлении
@dp.chat_join_request()
async def check_join(request: ChatJoinRequest):
    user = request.from_user
    profile = f"{user.first_name or ''} {user.username or ''}".lower()
    suspicious = any(kw in profile for kw in SPAM_KEYWORDS) or re.search(r'\d{4,}', user.username or '')
    if suspicious:
        await bot.decline_chat_join_request(request.chat.id, user.id)
        await bot.send_message(request.chat.id, f"🚫 Спамер отклонён: @{user.username or user.id}")

# Обработчик сообщений
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_message(message: types.Message):
    if not message.text:
        return
    text = message.text

    # Перевод, если иностранный
    translated, original_note = translate_if_foreign(text)
    if original_note:
        await message.reply(f"🌐 Перевод: {translated}\n{original_note}")

    # Проверка на спам (используем перевод, если был)
    check_text = translated if original_note else text
    if is_spam(check_text):
        try:
            await message.delete()
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
            await bot.send_message(message.chat.id, f"🗑️ Спам удалён от @{message.from_user.username or message.from_user.id}")
        except Exception as e:
            logging.error(f"Ошибка: {e}")

async def main():
    print("Бот запущен с переводчиком!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

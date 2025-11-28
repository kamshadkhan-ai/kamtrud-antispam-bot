import asyncio
import logging
import json
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ChatJoinRequest

# ←←← ТВОЙ ТОКЕН ←←←
BOT_TOKEN = "8281330001:AAEutOYVJ9OpCO1cwvoJDxb81ZnSFR8CNsI"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранение спам/не-спам
DB_FILE = "data.json"
spam_patterns = set()
ham_patterns = set()

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            global spam_patterns, ham_patterns
            spam_patterns = set(data.get("spam", []))
            ham_patterns = set(data.get("ham", []))

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"spam": list(spam_patterns), "ham": list(ham_patterns)}, f, ensure_ascii=False)

load_db()

# Слова для моментального бана
SPAM_WORDS = [
    "в/у", "права", "гибдд", "купить права", "без экзаменов",
    "трейдинг", "сигналы", "заработок", "быстрые деньги", "пассивный доход",
    "airdrop", "раздача", "free money", "1000$"
]
BAD_WORDS = ["бля", "пизд", "хуй", "еб", "пидор", "сука", "нахуй", "блять", "fuck", "shit", "bitch"]

def is_spam(text: str) -> bool:
    t = text.lower()
    if any(w in t for w in SPAM_WORDS + BAD_WORDS):
        return True
    if any(p.lower() in t for p in spam_patterns):
        return True
    if any(p.lower() in t for p in ham_patterns):
        return False
    return False

@dp.message(Command("start"))
async def start_cmd(m: types.Message):
    await m.answer("Бот работает! Добавь в группу как админа.")

@dp.message(Command("spam"))
async def mark_spam(m: types.Message):
    if m.reply_to_message and m.reply_to_message.text:
        spam_patterns.add(m.reply_to_message.text)
        save_db()
        await m.answer("Запомнил как спам")
    else:
        await m.answer("Ответь на сообщение /spam")

@dp.message(Command("ham"))
async def mark_ham(m: types.Message):
    if m.reply_to_message and m.reply_to_message.text:
        ham_patterns.add(m.reply_to_message.text)
        save_db()
        await m.answer("Запомнил как НЕ спам")
    else:
        await m.answer("Ответь на сообщение /ham")

# Бан спамеров при вступлении
@dp.chat_join_request()
async def join_check(req: ChatJoinRequest):
    user = req.from_user
    profile = f"{user.first_name or ''} {user.username or ''}".lower()
    if any(w in profile for w in SPAM_WORDS) or re.search(r"\d{5,}", profile):
        await bot.decline_chat_join_request(req.chat.id, user.id)
        await bot.send_message(req.chat.id, f"Спамер отклонён @{user.username or user.id}")

# Удаление спама в чате
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def check_message(m: types.Message):
    if not m.text:
        return
    if is_spam(m.text):
        try:
            await m.delete()
            await bot.ban_chat_member(m.chat.id, m.from_user.id)
            await m.answer(f"Спам удалён и пользователь забанен")
        except:
            pass  # нет прав — просто молчим

async def main():
    print("Бот запущен и работает 24/7!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

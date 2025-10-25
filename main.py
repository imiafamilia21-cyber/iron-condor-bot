import os
from fastapi import FastAPI
from aiogram import Bot
from aiogram.types import Message
import asyncio

app = FastAPI()

# Функция отправки сообщения в Telegram
async def send_telegram(message: str):
    TELEGRAM_TOKEN = os.getenv("8059438282:AAHgxgHlzVIGf-iClBtHi_QGdZSPfzeC-pY")
    CHAT_ID = os.getenv("1913932382")
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_TOKEN или CHAT_ID не заданы")
        return
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)

# Основная логика стратегии Iron Condor
def run_iron_condor():
    # Пример данных — можно заменить на реальные расчёты
    spot = 3962.11
    expiry = "26.10.2025"
    legs = ["ETH-USD-251026-3850-P", "ETH-USD-251026-3900-P", "ETH-USD-251026-4000-C", "ETH-USD-251026-4050-C"]
    premium = 0.01
    max_loss = 99.99
    max_profit = 0.01

    message = (
        f"✅ Открыта конструкция Iron Condor\n"
        f"Спот: {spot}\n"
        f"Экспирация: {expiry}\n"
        f"Премия: {premium}\n"
        f"Риск: {max_loss}\n"
        f"Потенциал: {max_profit}\n"
        f"Страйки: {legs}"
    )

    # Отправка сообщения в Telegram
    asyncio.run(send_telegram(message))

    # Возврат JSON-ответа
    return {
        "spot": spot,
        "expiry": expiry,
        "legs": legs,
        "premium": premium,
        "risk": max_loss,
        "potential": max_profit,
        "orders": [
            {"order": "buy", "instId": legs[0], "code": "1"},
            {"order": "sell", "instId": legs[1], "code": "1"},
            {"order": "sell", "instId": legs[2], "code": "1"},
            {"order": "buy", "instId": legs[3], "code": "1"},
        ]
    }

# Маршрут /
@app.get("/")
def run():
    return run_iron_condor()

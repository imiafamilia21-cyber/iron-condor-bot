# 📦 Импорт библиотек
import os
import json
import csv
import logging
import hashlib
from datetime import datetime
from fastapi import FastAPI, Response, Request
from aiogram import Bot
import asyncio

# 🚀 Инициализация FastAPI и логов
app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# 📁 Файлы для хранения истории и экспорта
HISTORY_FILE = "history.json"
CSV_FILE = "history.csv"

# 🔐 Загрузка переменных окружения (ключи Telegram)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 📤 Отправка сообщения в Telegram
async def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning("❌ TELEGRAM_TOKEN или CHAT_ID не заданы")
        return
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)

# 🔐 Хеширование сделки для защиты от подделки
def hash_deal(deal: dict) -> str:
    raw = json.dumps(deal, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

# 💾 Сохранение сделки в файл истории
def save_to_history(data: dict):
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        else:
            history = []
        history.append(data)
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении истории: {e}")

# 📈 Основная стратегия Iron Condor
async def run_iron_condor():
    # Пример параметров сделки
    spot = 3962.11
    expiry = "26.10.2025"
    legs = ["ETH-USD-251026-3850-P", "ETH-USD-251026-3900-P", "ETH-USD-251026-4000-C", "ETH-USD-251026-4050-C"]
    premium = 0.01
    max_loss = 99.99
    max_profit = 0.01

    # Формирование сообщения
    message = (
        f"✅ Открыта конструкция Iron Condor\n"
        f"Спот: {spot}\n"
        f"Экспирация: {expiry}\n"
        f"Премия: {premium}\n"
        f"Риск: {max_loss}\n"
        f"Потенциал: {max_profit}\n"
        f"Страйки: {legs}"
    )

    logging.info("📈 Открытие позиции")
    logging.info(message)

    await send_telegram(message)

    # Формирование сделки
    deal = {
        "timestamp": datetime.utcnow().isoformat(),
        "spot": spot,
        "expiry": expiry,
        "legs": legs,
        "premium": premium,
        "risk": max_loss,
        "potential": max_profit,
        "status": "open"
    }

    # Добавление хеша
    deal["hash"] = hash_deal(deal)

    save_to_history(deal)
    return deal

# 🔗 Запуск стратегии через браузер
@app.get("/")
async def run():
    return await run_iron_condor()

# 📜 Получение всей истории сделок
@app.get("/history")
def get_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

# 📊 Метрики стратегии
@app.get("/metrics")
def get_metrics():
    if not os.path.exists(HISTORY_FILE):
        return {"total": 0, "average_premium": 0, "average_risk": 0}
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)
    total = len(history)
    avg_premium = sum(d["premium"] for d in history) / total
    avg_risk = sum(d["risk"] for d in history) / total
    return {
        "total": total,
        "average_premium": round(avg_premium, 4),
        "average_risk": round(avg_risk, 2)
    }

# 📤 Экспорт истории в CSV
@app.get("/export")
def export_csv():
    if not os.path.exists(HISTORY_FILE):
        return {"error": "Нет данных для экспорта"}
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)
    with open(CSV_FILE, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["timestamp", "spot", "expiry", "legs", "premium", "risk", "potential", "status", "result", "hash"])
        for d in history:
            writer.writerow([
                d["timestamp"], d["spot"], d["expiry"], ",".join(d["legs"]),
                d["premium"], d["risk"], d["potential"], d["status"],
                d.get("result", ""), d.get("hash", "")
            ])
    with open(CSV_FILE, "r") as f:
        return Response(content=f.read(), media_type="text/csv")

# 📋 Визуальный отчёт с фильтрацией
@app.get("/report")
def get_report(request: Request):
    params = request.query_params
    start = params.get("start")
    end = params.get("end")
    status = params.get("status")

    if not os.path.exists(HISTORY_FILE):
        return Response(content="<h2>Нет данных</h2>", media_type="text/html")
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)

    filtered = []
    for d in history:
        if status and d["status"] != status:
            continue
        if start and d["timestamp"] < start:
            continue
        if end and d["timestamp"] > end:
            continue
        filtered.append(d)

    html = "<h2>Отчёт по сделкам</h2><table border='1'><tr><th>ID</th><th>Дата</th><th>Спот</th><th>Премия</th><th>Риск</th><th>Потенциал</th><th>Статус</th><th>Результат</th></tr>"
    for i, d in enumerate(filtered):
        html += f"<tr><td>{i}</td><td>{d['timestamp']}</td><td>{d['spot']}</td><td>{d['premium']}</td><td>{d['risk']}</td><td>{d['potential']}</td><td>{d['status']}</td><td>{d.get('result','')}</td></tr>"
    html += "</table>"
    return Response(content=html, media_type="text/html")

# ✅ Закрытие позиции с результатом
@app.post("/close")
def close_position(id: int, result: str):
    if not os.path.exists(HISTORY_FILE):
        return {"error": "История не найдена"}
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)
    if id >= len(history):
        return {"error": "Неверный ID"}
    history[id]["status"] = "closed"
    history[id]["result"] = result
    history[id]["closed_at"] = datetime.utcnow().isoformat()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    return {"message": f"Сделка {id} закрыта с результатом: {result}"}

# 📤 Отправка аудита в Telegram
async def send_audit():
    if not os.path.exists(HISTORY_FILE):
        return
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)
    total = len(history)
    closed = sum(1 for d in history if d["status"] == "closed")
    profit = sum(1 for d in history if d.get("result") == "profit")
    loss = sum(1 for d in history if d.get("result") == "loss")
    message = (
        f"📊 Аудит стратегии:\n"
        f"Всего сделок: {total}\n"
        f"Закрыто: {closed}\n"
        f"Прибыльных: {profit}\n"
        f"Убыточных: {loss}"
    )
    await send_telegram(message)

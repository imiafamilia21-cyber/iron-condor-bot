from datetime import datetime, timezone
import hmac, base64, hashlib, requests, json
from fastapi import FastAPI
from aiogram import Bot
import asyncio
import os

# 🔐 Переменные окружения
API_KEY = "226434d8-393c-40de-a08b-6ceb87a184dc"
API_SECRET = "69C3EB64C283FD2BABD9468D0975E90E"
PASSPHRASE = "TC-iq[H^-})1"
BASE_URL = "https://www.okx.com"
TELEGRAM_TOKEN = os.getenv("8059438282:AAHgxgHlzVIGf-iClBtHi_QGdZSPfzeC-pY")
CHAT_ID = os.getenv("1913932382")

# 📩 Telegram-бот
bot = Bot(token=TELEGRAM_TOKEN)

async def notify(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)

def send_telegram(text):
    asyncio.run(notify(text))

def get_iso_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def get_headers(timestamp, sign):
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
        "x-simulated-trading": "1"
    }

def generate_signature(timestamp, method, request_path, body):
    body_str = json.dumps(body) if body else ""
    message = f"{timestamp}{method}{request_path}{body_str}"
    mac = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def send_request(method, path, body=None):
    timestamp = get_iso_timestamp()
    sign = generate_signature(timestamp, method, path, body)
    headers = get_headers(timestamp, sign)
    url = BASE_URL + path
    if method == "GET":
        response = requests.get(url, headers=headers, params=body)
    else:
        response = requests.request(method, url, headers=headers, json=body)
    return response.json()

def get_eth_price():
    result = send_request("GET", "/api/v5/market/ticker", {"instId": "ETH-USDT"})
    return float(result["data"][0]["last"])

def get_eth_options():
    result = send_request("GET", "/api/v5/public/instruments", {
        "instType": "OPTION",
        "uly": "ETH-USD"
    })
    return result["data"]

def extract_strike(instId):
    try:
        parts = instId.split("-")
        return float(parts[3])
    except:
        return None

def get_option_price(instId):
    result = send_request("GET", "/api/v5/market/ticker", {"instId": instId})
    try:
        price_str = result["data"][0]["last"]
        return float(price_str) if price_str else 0.0
    except:
        return 0.0

def calculate_condor_metrics(legs):
    prices = [get_option_price(inst) for inst in legs]
    premium = (prices[1] - prices[0]) + (prices[2] - prices[3])
    width = abs(extract_strike(legs[2]) - extract_strike(legs[1]))
    max_profit = round(premium, 2)
    max_loss = round(width - premium, 2)
    return round(premium, 2), width, max_profit, max_loss

def find_condor_legs(options, spot):
    enriched = []
    for opt in options:
        strike = extract_strike(opt.get("instId", ""))
        if strike:
            opt["strike"] = strike
            enriched.append(opt)

    strikes = sorted(set(opt["strike"] for opt in enriched))
    lower_put = min(strikes, key=lambda x: abs(x - (spot - 100)))
    inner_put = min(strikes, key=lambda x: abs(x - (spot - 50)))
    inner_call = min(strikes, key=lambda x: abs(x - (spot + 50)))
    upper_call = min(strikes, key=lambda x: abs(x - (spot + 100)))

    expiry = sorted(set(opt["expTime"] for opt in enriched if opt["expTime"]))
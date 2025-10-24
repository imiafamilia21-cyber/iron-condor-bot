import time
import hmac
import base64
import hashlib
import requests
import json
import csv
from datetime import datetime, timezone

API_KEY = "226434d8-393c-40de-a08b-6ceb87a184dc"
API_SECRET = "69C3EB64C283FD2BABD9468D0975E90E"
PASSPHRASE = "TC-iq[H^-})1"
BASE_URL = "https://www.okx.com"

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
    except Exception as e:
        print(f"⚠️ Ошибка получения цены для {instId}: {e}")
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

    if not enriched:
        print("❌ Не удалось восстановить страйки из instId.")
        return []

    strikes = sorted(set(opt["strike"] for opt in enriched))
    print(f"✅ Восстановлено {len(strikes)} страйков. Примеры: {strikes[:5]} ... {strikes[-5:]}")

    lower_put = min(strikes, key=lambda x: abs(x - (spot - 100)))
    inner_put = min(strikes, key=lambda x: abs(x - (spot - 50)))
    inner_call = min(strikes, key=lambda x: abs(x - (spot + 50)))
    upper_call = min(strikes, key=lambda x: abs(x - (spot + 100)))

    expiry = sorted(set(opt["expTime"] for opt in enriched if opt["expTime"]))[0]
    print(f"📅 Используем экспирацию: {expiry}")

    legs = []
    for strike, side, opt_type in [
        (lower_put, "buy", "P"),
        (inner_put, "sell", "P"),
        (inner_call, "sell", "C"),
        (upper_call, "buy", "C")
    ]:
        inst = next((opt for opt in enriched if opt["strike"] == strike and opt["optType"] == opt_type and opt["expTime"] == expiry), None)
        if inst:
            legs.append(inst["instId"])
        else:
            print(f"⚠️ Не найдена нога: {side} {opt_type} @ {strike}")
    return legs

def log_trade(instId, side, spot, strategy="Iron Condor", premium=None, width=None, max_profit=None, max_loss=None):
    with open("trade_report.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().isoformat(),
            instId,
            side,
            spot,
            strategy,
            premium,
            width,
            max_profit,
            max_loss
        ])

def place_order(instId, side, spot, premium=None, width=None, max_profit=None, max_loss=None):
    order = {
        "instId": instId,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market",
        "sz": "0.05"
    }
    result = send_request("POST", "/api/v5/trade/order", order)
    print(f"{side.upper()} {instId} → {result.get('code')}")
    log_trade(instId, side, spot, premium, width, max_profit, max_loss)

def get_balance():
    result = send_request("GET", "/api/v5/account/balance")
    balances = result.get("data", [])[0].get("details", [])
    print("💰 Баланс аккаунта:")
    for asset in balances:
        print(f" - {asset['ccy']}: {asset['availBal']} доступно")

if __name__ == "__main__":
    print("📡 Получаем цену ETH...")
    spot = get_eth_price()
    print(f"📈 ETH spot: ${spot:.2f}")

    print("💰 Проверяем баланс...")
    get_balance()

    print("📦 Получаем список опционов...")
    options = get_eth_options()

    print("🧠 Строим Iron Condor...")
    legs = find_condor_legs(options, spot)
    if len(legs) == 4:
        print("📊 Считаем премию и риск...")
        premium, width, max_profit, max_loss = calculate_condor_metrics(legs)
        print(f"💰 Премия: {premium}, Риск: {max_loss}, Потенциал: {max_profit}")

        if premium == 0.0:
            print("❌ Конструкция неликвидна — премия отсутствует.")
        else:
            print("🚀 Размещаем ордера:")
            place_order(legs[0], "buy", spot, premium, width, max_profit, max_loss)
            place_order(legs[1], "sell", spot)
            place_order(legs[2], "sell", spot)
            place_order(legs[3], "buy", spot)
    else:
        print("❌ Не удалось построить конструкцию — проверь ликвидность или доступные страйки.")

from fastapi import FastAPI
from datetime import datetime, timezone
import hmac, base64, hashlib, requests, json, csv

app = FastAPI()

# 🔐 Вставь свои ключи
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
PASSPHRASE = "your_passphrase"
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

    expiry = sorted(set(opt["expTime"] for opt in enriched if opt["expTime"]))[0]

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
    return legs, expiry

def place_order(instId, side):
    order = {
        "instId": instId,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market",
        "sz": "0.05"
    }
    result = send_request("POST", "/api/v5/trade/order", order)
    return result.get("code")

@app.get("/run")
def run_iron_condor():
    spot = get_eth_price()
    options = get_eth_options()
    legs, expiry = find_condor_legs(options, spot)

    if len(legs) != 4:
        return {"error": "Недостаточно ликвидности или страйков"}

    premium, width, max_profit, max_loss = calculate_condor_metrics(legs)

    if premium == 0.0:
        return {"error": "Премия нулевая — конструкция неликвидна"}

    results = []
    results.append({"order": "buy", "instId": legs[0], "code": place_order(legs[0], "buy")})
    results.append({"order": "sell", "instId": legs[1], "code": place_order(legs[1], "sell")})
    results.append({"order": "sell", "instId": legs[2], "code": place_order(legs[2], "sell")})
    results.append({"order": "buy", "instId": legs[3], "code": place_order(legs[3], "buy")})

    return {
        "spot": spot,
        "expiry": expiry,
        "legs": legs,
        "premium": premium,
        "risk": max_loss,
        "potential": max_profit,
        "orders": results
    }

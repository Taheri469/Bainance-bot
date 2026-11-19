import requests
import time

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

while True:
    for symbol in SYMBOLS:
        url = "https://api.binance.com/api/v3/ticker/price"
        data = requests.get(url, params={"symbol": symbol}).json()
        print(symbol, data["price"])

    print("----------------")
    time.sleep(10)

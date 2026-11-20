import ccxt
import pandas as pd
import time
import os
exchange = ccxt.binance({
    "apiKey": os.getenv("BINANCE_API_KEY"),
    "secret": os.getenv("BINANCE_API_SECRET"),
    "enableRateLimit": True,
})
symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

while True:

    for symbol in symbols:

        candles = exchange.fetch_ohlcv(

            symbol, timeframe="5m", limit=100

        )

        df = pd.DataFrame(candles, columns=[

            "time", "open", "high", "low", "close", "volume"

        ])

        df["EMA9"] = df["close"].ewm(span=9).mean()

        df["EMA21"] = df["close"].ewm(span=21).mean()

        delta = df["close"].diff()

        gain = delta.clip(lower=0)

        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()

        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

        rs = avg_gain / avg_loss

        df["RSI"] = 100 - (100 / (1 + rs))

        price = df["close"].iloc[-1]

        ema9 = df["EMA9"].iloc[-1]

        ema21 = df["EMA21"].iloc[-1]

        rsi = df["RSI"].iloc[-1]

        if ema9 > ema21 and rsi > 50:

            signal = "LONG"

            stop_loss = price * 0.99

            take_profit = price * 1.02

        elif ema9 < ema21 and rsi < 50:

            signal = "SHORT"

            stop_loss = price * 1.01

            take_profit = price * 0.98

        else:

            signal = "WAIT"

            stop_loss = 0

            take_profit = 0

        print(f"\n{symbol}")

        print(f"Preis: {price:.2f}")

        print(f"RSI: {rsi:.2f}")

        print(f"Signal: {signal}")

        print(f"Stop-Loss: {stop_loss:.2f}")

        print(f"Take-Profit: {take_profit:.2f}")

    print("------------------------")

    time.sleep(60)

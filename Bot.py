import ccxt
import pandas as pd
import time

exchange = ccxt.binance()

symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

while True:
    for symbol in symbols:
        candles = exchange.fetch_ohlcv(
            symbol, timeframe="5m", limit=50
        )

        df = pd.DataFrame(
            candles,
            columns=["time", "open", "high", "low", "close", "volume"]
        )

        df["EMA9"] = df["close"].ewm(span=9).mean()
        df["EMA21"] = df["close"].ewm(span=21).mean()

        ema9 = df["EMA9"].iloc[-1]
        ema21 = df["EMA21"].iloc[-1]
        price = df["close"].iloc[-1]

        if ema9 > ema21:
            signal = "LONG"
        elif ema9 < ema21:
            signal = "SHORT"
        else:
            signal = "WAIT"

        print(symbol, price, signal)

    print("----------------")
    time.sleep(60)

import ccxt
import os
import time
import pandas as pd
from datetime import datetime

# ==================================
# EINSTELLUNGEN
# ==================================

LIVE_TRADING = False  # Noch nicht aktivieren!

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAME = "5m"

MAX_LEVERAGE = 2
MAX_RISK_USDT = 0.50
MAX_MARGIN_FRACTION = 0.25

STOP_LOSS_PERCENT = 0.01
TAKE_PROFIT_PERCENT = 0.02

CHECK_INTERVAL = 60

# ==================================
# BINANCE VERBINDUNG
# ==================================

exchange = ccxt.binance({
    "apiKey": os.getenv("BINANCE_API_KEY"),
    "secret": os.getenv("BINANCE_API_SECRET"),
    "enableRateLimit": True,
    "options": {
        "defaultType": "future"
    }
})

exchange.load_markets()


# ==================================
# KONTOSTAND
# ==================================

def get_balance():
    balance = exchange.fetch_balance()
    return float(balance["USDT"]["free"])


# ==================================
# OFFENE POSITIONEN
# ==================================

def get_open_positions():
    positions = exchange.fetch_positions()

    return [
        p for p in positions
        if abs(float(p.get("contracts") or 0)) > 0
    ]


# ==================================
# SIGNAL BERECHNEN
# ==================================

def get_signal(symbol):

    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe=TIMEFRAME,
        limit=100
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "time", "open", "high",
            "low", "close", "volume"
        ]
    )

    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema21"] = df["close"].ewm(span=21).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    # Letzte abgeschlossene Kerze
    last = df.iloc[-2]

    price = float(last["close"])
    ema9 = float(last["ema9"])
    ema21 = float(last["ema21"])
    rsi = float(last["rsi"])

    signal = "WAIT"

    if ema9 > ema21 and rsi > 52:
        signal = "LONG"

    elif ema9 < ema21 and rsi < 48:
        signal = "SHORT"

    return signal, price, rsi


# ==================================
# POSITIONSGRÖSSE
# ==================================

def calculate_quantity(symbol, price, balance):

    market = exchange.market(symbol)

    risk_size = MAX_RISK_USDT / STOP_LOSS_PERCENT

    margin_limit = (
        balance *
        MAX_MARGIN_FRACTION *
        MAX_LEVERAGE
    )

    notional = min(risk_size, margin_limit)

    quantity = notional / price

    quantity = float(
        exchange.amount_to_precision(symbol, quantity)
    )

    minimum = market["limits"]["cost"]["min"]

    if quantity * price < minimum:
        return 0

    return quantity


# ==================================
# BINANCE ALGO SCHUTZORDERS
# ==================================

def place_protection(symbol, side, stop_price, tp_price):

    market = exchange.market(symbol)
    opposite_side = "SELL" if side == "BUY" else "BUY"

    def create_algo(order_type, trigger):
        return exchange.fapiPrivatePostAlgoOrder({
            "algoType": "CONDITIONAL",
            "symbol": market["id"],
            "side": opposite_side,
            "type": order_type,
            "triggerPrice": exchange.price_to_precision(
                symbol, trigger
            ),
            "workingType": "MARK_PRICE",
            "closePosition": "true"
        })

    sl = create_algo("STOP_MARKET", stop_price)
    tp = create_algo("TAKE_PROFIT_MARKET", tp_price)

    return sl, tp


# ==================================
# TRADE AUSFÜHREN
# ==================================

def execute_trade(symbol, signal, price, balance):

    if not LIVE_TRADING:
        print("ECHTHANDEL GESPERRT – nur Signalanzeige.")
        return

    if not hasattr(exchange, "fapiPrivatePostAlgoOrder"):
        print("FEHLER: Binance Algo-Order-Schnittstelle fehlt.")
        return

    quantity = calculate_quantity(
        symbol, price, balance
    )

    if quantity <= 0:
        print("Mindestorder nicht erreicht.")
        return

    side = "BUY" if signal == "LONG" else "SELL"

    exchange.set_leverage(MAX_LEVERAGE, symbol)

    print("Sende Market-Order:", symbol, signal)

    order = exchange.create_order(
        symbol,
        "market",
        side.lower(),
        quantity
    )

    if order.get("status") != "closed" and not order.get("filled"):
        print("Order nicht eindeutig ausgeführt. Bitte prüfen!")
        return

    entry = float(order.get("average") or price)

    if signal == "LONG":
        stop = entry * (1 - STOP_LOSS_PERCENT)
        target = entry * (1 + TAKE_PROFIT_PERCENT)
    else:
        stop = entry * (1 + STOP_LOSS_PERCENT)
        target = entry * (1 - TAKE_PROFIT_PERCENT)

    try:
        sl, tp = place_protection(
            symbol, side, stop, target
        )

        print("Position eröffnet und Schutzorders bestätigt.")
        print("Stop-Loss:", sl)
        print("Take-Profit:", tp)

    except Exception as error:

        print("SCHUTZORDER FEHLER:", error)
        print("Position muss sofort überprüft und abgesichert werden!")

        try:
            exchange.fapiPrivateDeleteAlgoOpenOrders({
                "symbol": exchange.market(symbol)["id"]
            })
        except Exception as cancel_error:
            print("Algo-Storno fehlgeschlagen:", cancel_error)

        try:
            exchange.create_order(
                symbol,
                "market",
                "sell" if side == "BUY" else "buy",
                quantity,
                None,
                {"reduceOnly": True}
            )
            print("Notfallschließung gesendet.")

        except Exception as close_error:
            print("KRITISCH: Position manuell prüfen:", close_error)


# ==================================
# HAUPTPROGRAMM
# ==================================

def main():

    print("\n==============================")
    print("BINANCE FUTURES BOT")
    print("==============================")

    print("Live-Trading:", LIVE_TRADING)

    while True:

        try:
            balance = get_balance()

            print("\nZeit:", datetime.now())
            print("Freies Guthaben:", balance, "USDT")

            positions = get_open_positions()

            print("Offene Positionen:", len(positions))

            if positions:
                print("Position vorhanden – keine neue Order.")
                time.sleep(CHECK_INTERVAL)
                continue

            for symbol in SYMBOLS:

                signal, price, rsi = get_signal(symbol)

                print("\n", symbol)
                print("Preis:", price)
                print("RSI:", round(rsi, 2))
                print("Signal:", signal)

                if signal in ["LONG", "SHORT"]:
                    execute_trade(
                        symbol,
                        signal,
                        price,
                        balance
                    )
                    break

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("Bot gestoppt.")
            break

        except Exception as error:
            print("BOT FEHLER:", error)
            time.sleep(30)


if __name__ == "__main__":
    main()

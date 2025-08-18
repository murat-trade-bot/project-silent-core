# coin_scanner.py
"""
Çoklu coin tarama ve en iyi coini otomatik seçen modül
"""

import json
import time
import logging
from typing import List, Dict, Any, Optional
from modules.trend_signals import detect_buy_signal, detect_strong_reversal_sell

COIN_LIST_PATH = 'config/coin_list.json'

def load_coin_list() -> List[str]:
    with open(COIN_LIST_PATH, 'r') as f:
        return json.load(f)


def fetch_candles_and_volumes(client, symbol: str, interval: str = '1m', limit: int = 30):
    """
    Binance API'den mum, hacim, kapanış fiyatı, RSI ve EMA dizileri çeker.
    """
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        closes = [float(k[4]) for k in klines]
        candles = [{'open': float(k[1]), 'close': float(k[4])} for k in klines]
        volumes = [float(k[5]) for k in klines]
        rsi_series = calculate_rsi_series(closes, period=14)
        ema_series = calculate_ema_series(closes, period=14)
        return candles, volumes, closes, rsi_series, ema_series
    except Exception as e:
        logging.error(f"API veri çekim hatası: {symbol} - {e}")
        return None, None, None, None, None


def calculate_rsi_series(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """RSI serisi döndürür."""
    if len(closes) < period + 1:
        return [None] * len(closes)
    rsi_list = [None] * period
    for i in range(period, len(closes)):
        gains = [max(0, closes[j] - closes[j-1]) for j in range(i-period+1, i+1)]
        losses = [max(0, closes[j-1] - closes[j]) for j in range(i-period+1, i+1)]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        rsi_list.append(rsi)
    return rsi_list


def calculate_ema_series(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """EMA serisi döndürür."""
    if len(closes) < period:
        return [None] * len(closes)
    ema_list = [None] * (period-1)
    ema = sum(closes[:period]) / period
    ema_list.append(ema)
    multiplier = 2 / (period + 1)
    for price in closes[period:]:
        ema = (price - ema) * multiplier + ema
        ema_list.append(ema)
    return ema_list



def load_scoring_params(path: str = 'config/coin_scanner_params.json') -> dict:
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        # Varsayılan parametreler
        return {
            "buy_signal_weight": 2,
            "reversal_penalty": -2,
            "no_reversal_bonus": 1,
            "vol_change_scale": 10,
            "vol_change_clip": 2,
            "volatility_clip": 2,
            "rsi_oversold": 2,
            "rsi_mid": 1,
            "rsi_overbought": -1,
            "ema_above": 1,
            "ema_below": -1
        }

def select_best_coin(client, sleep_time: float = 0.2, verbose: bool = False, scoring_params: dict = None) -> Optional[str]:
    """
    Çoklu coin taraması yapar, gelişmiş skor sistemiyle en iyi coini seçer.
    """
    coin_list = load_coin_list()
    if scoring_params is None:
        scoring_params = load_scoring_params()
    best_score = float('-inf')
    best_coin = None
    for symbol in coin_list:
        candles, volumes, closes, rsi_series, ema_series = fetch_candles_and_volumes(client, symbol, '1m', 30)
        if candles is None or volumes is None or closes is None:
            continue

        # Hacim artışı yüzdesi (son 2 bar)
        if len(volumes) >= 4:
            vol_change = ((volumes[-1] - volumes[-4]) / (volumes[-4] + 1e-8)) * 100
        else:
            vol_change = 0

        # Volatilite (son 10 barın stdev'i)
        if len(closes) >= 10:
            mean = sum(closes[-10:]) / 10
            variance = sum((x - mean) ** 2 for x in closes[-10:]) / 10
            volatility = variance ** 0.5
        else:
            volatility = 0

        # RSI/EMA uyumu (son 3 bar ortalaması)
        rsi_score = 0
        ema_score = 0
        rsi_last = [r for r in rsi_series[-3:] if r is not None]
        ema_last = [e for e in ema_series[-3:] if e is not None]
        rsi_val = sum(rsi_last) / len(rsi_last) if rsi_last else None
        ema_val = sum(ema_last) / len(ema_last) if ema_last else None
        if rsi_val is not None:
            if 30 < rsi_val < 70:
                rsi_score = scoring_params["rsi_mid"]
            elif rsi_val <= 30:
                rsi_score = scoring_params["rsi_oversold"]
            elif rsi_val >= 70:
                rsi_score = scoring_params["rsi_overbought"]
        if ema_val is not None and closes[-1] > ema_val:
            ema_score = scoring_params["ema_above"]
        elif ema_val is not None:
            ema_score = scoring_params["ema_below"]

        # Trend sinyalleri (son 3 bar)
        buy_signal = detect_buy_signal(candles[-5:], volumes[-5:])
        reversal_signal = detect_strong_reversal_sell(
            candles[-5:],
            closes[-5:],
            volumes[-5:],
            rsi_series[-5:] if rsi_series else [None]*5,
            ema_series[-5:] if ema_series else [None]*5
        )

        # Skor hesaplama
        score = 0
        score += scoring_params["buy_signal_weight"] if buy_signal else 0
        score += scoring_params["no_reversal_bonus"] if not reversal_signal else scoring_params["reversal_penalty"]
        score += min(max(vol_change / scoring_params["vol_change_scale"], -scoring_params["vol_change_clip"]), scoring_params["vol_change_clip"])
        score += min(max(volatility, 0), scoring_params["volatility_clip"])
        score += rsi_score
        score += ema_score

        # Momentum: son 3 bar kapanış değişimi
        if len(closes) >= 4:
            momentum = closes[-1] - closes[-4]
            score += min(max(momentum, -2), 2)

        if verbose:
            print(f"{symbol}: score={score:.2f} vol%={vol_change:.1f} volat={volatility:.4f} rsi={rsi_val} ema={ema_val} buy={buy_signal} rev={reversal_signal}")

        if score > best_score:
            best_score = score
            best_coin = symbol

        time.sleep(sleep_time)  # API rate limit koruması
    return best_coin



def test_select_best_coin():
    """
    select_best_coin fonksiyonunun testini mock client ile yapar. Edge-case ve hata testleri de içerir.
    """
    class MockClient:
        def get_klines(self, symbol, interval, limit):
            import random
            if symbol == "FAILCOIN":
                raise Exception("API Fail")
            base = random.uniform(10, 100)
            closes = [base + random.uniform(-1, 1) for _ in range(limit)]
            volumes = [random.uniform(100, 1000) for _ in range(limit)]
            return [
                [0, closes[i], 0, 0, closes[i], volumes[i], 0, 0, 0, 0, 0, 0]
                for i in range(limit)
            ]

    import os
    test_coins = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "FAILCOIN"]
    os.makedirs("config", exist_ok=True)
    with open(COIN_LIST_PATH, 'w') as f:
        json.dump(test_coins, f)

    # Parametre dosyası örneği
    params = {
        "buy_signal_weight": 2,
        "reversal_penalty": -2,
        "no_reversal_bonus": 1,
        "vol_change_scale": 10,
        "vol_change_clip": 2,
        "volatility_clip": 2,
        "rsi_oversold": 2,
        "rsi_mid": 1,
        "rsi_overbought": -1,
        "ema_above": 1,
        "ema_below": -1
    }
    with open('config/coin_scanner_params.json', 'w') as f:
        json.dump(params, f)

    mock_client = MockClient()
    result = select_best_coin(mock_client, sleep_time=0, verbose=True)
    print(f"Test sonucu: En iyi coin: {result}")

    # Edge-case: Tüm coinler API hatası verirse
    class AllFailClient:
        def get_klines(self, symbol, interval, limit):
            raise Exception("API Fail")
    result2 = select_best_coin(AllFailClient(), sleep_time=0, verbose=True)
    print(f"Test sonucu (tümü fail): {result2}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_select_best_coin()

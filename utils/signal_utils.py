import time
from onchain_alternative import get_trade_signal
from core.logger import BotLogger

logger = BotLogger()
_rate_limit_logged = set()
_monthly_cap_logged = False
_invalid_symbol_logged = set()

def safe_get_trade_signal(symbol: str, coin_id: str) -> dict:
    MAX_RETRIES, _BASE_DELAY = 3, 2
    global _monthly_cap_logged
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_trade_signal(symbol, coin_id)
        except Exception as e:
            msg = str(e)
            # Twitter rate limit (429)
            if "429" in msg or "Too Many Requests" in msg:
                if attempt < MAX_RETRIES:
                    time.sleep(_BASE_DELAY ** attempt)
                    continue
                if symbol not in _rate_limit_logged:
                    logger.warning(f"Twitter rate limit aşıldı ({symbol}), sessize alınıyor.")
                    _rate_limit_logged.add(symbol)
                return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
            # On-chain aylık kota limiti
            elif "Usage cap exceeded" in msg:
                if not _monthly_cap_logged:
                    logger.warning("On-chain aylık kota aşıldı, atlanıyor.")
                    _monthly_cap_logged = True
                return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
            # Invalid symbol hatası
            elif "Invalid symbol" in msg or "invalid symbol" in msg:
                if symbol not in _invalid_symbol_logged:
                    logger.info(f"{symbol} için geçersiz sembol, atlanıyor.")
                    _invalid_symbol_logged.add(symbol)
                return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
            else:
                logger.error(f"Sinyal alınırken hata ({symbol}): {e}")
                return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
    return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}

def calculate_rsi(closes, period=14):
    if len(closes) < period:
        return [None] * len(closes)
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi = []
    for i in range(period, len(closes)):
        if i == period:
            rs = avg_gain / avg_loss if avg_loss != 0 else 0
        else:
            avg_gain = (avg_gain * (period - 1) + gains[i-1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i-1]) / period
            rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi.append(100 - (100 / (1 + rs)))
    return [None] * (period) + rsi

def calculate_ema(closes, period=9):
    if len(closes) < period:
        return [None] * len(closes)
    ema = []
    k = 2 / (period + 1)
    ema.append(sum(closes[:period]) / period)
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return [None] * (period - 1) + ema
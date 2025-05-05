import random from datetime import datetime, timedelta

from config import settings from modules.time_strategy import get_current_strategy_mode from core.logger import BotLogger from modules.sentiment_analysis import analyze_sentiment from modules.onchain_tracking import track_onchain_activity from modules.technical_analysis import ( fetch_ohlcv_from_binance, calculate_rsi, calculate_macd, calculate_atr )

logger = BotLogger()

class Strategy: """ Decision engine combining multi-timeframe technicals, sentiment & on-chain signals, regime detection via period targets, and dynamic risk management for fully autonomous trading. Supports BUY, SELL, HOLD decisions with minimum hold time, stop-loss and take-profit enforcement. """ MIN_HOLD_TIME = timedelta(minutes=5)

def __init__(self):
    # Track open positions: {symbol: datetime_opened}
    self.position_open_time = {}
    # Last decision: {symbol: "BUY"|"SELL"|"HOLD"}
    self.last_decision = {}

def reset(self):
    # Reset context (not clearing open positions)
    self.last_decision.clear()

def _get_signals(self, symbol):
    """
    Fetch market data and compute technical, sentiment, and on-chain signals.
    """
    # 1. Fetch OHLCV
    ohlcv = fetch_ohlcv_from_binance(symbol, interval=settings.CANDLE_INTERVAL, limit=settings.CANDLE_LIMIT)

    # 2. Compute technicals
    rsi = calculate_rsi(ohlcv)
    macd, macd_signal, _ = calculate_macd(ohlcv)
    atr = calculate_atr(ohlcv)

    # 3. Sentiment signal
    sentiment_score = analyze_sentiment(symbol)

    # 4. On-chain activity
    whale_activity = track_onchain_activity(symbol)

    return {
        'rsi': rsi,
        'macd': macd,
        'macd_signal': macd_signal,
        'atr': atr,
        'sentiment': sentiment_score,
        'onchain': whale_activity
    }

def decide(self, symbol):
    """
    Decide action: "BUY", "HOLD" or "SELL" for the given symbol.
    """
    now = datetime.utcnow()
    signals = self._get_signals(symbol)
    mode = get_current_strategy_mode()

    # If no open position for symbol
    if symbol not in self.position_open_time:
        # BUY conditions: oversold RSI and positive sentiment
        if signals['rsi'] < settings.RSI_OVERSOLD and signals['sentiment'] > settings.SENTIMENT_THRESHOLD:
            logger.info(f"Signal BUY for {symbol}: RSI={signals['rsi']}, Sentiment={signals['sentiment']}")
            self.position_open_time[symbol] = now
            self.last_decision[symbol] = 'BUY'
            return 'BUY'
        else:
            self.last_decision[symbol] = 'HOLD'
            return 'HOLD'

    # If there is an open position
    opened_at = self.position_open_time[symbol]
    held_duration = now - opened_at

    # Enforce minimum hold time
    if held_duration < self.MIN_HOLD_TIME:
        logger.info(f"HOLD {symbol}: minimum hold time not reached ({held_duration})")
        self.last_decision[symbol] = 'HOLD'
        return 'HOLD'

    # SELL conditions: overbought RSI, MACD crossover, extreme negative sentiment, on-chain whale sell
    if (
        signals['rsi'] > settings.RSI_OVERBOUGHT or
        (signals['macd'] < signals['macd_signal']) or
        signals['sentiment'] < -settings.SENTIMENT_THRESHOLD or
        signals['onchain'].get('large_sells', False)
    ):
        logger.info(f"Signal SELL for {symbol}: RSI={signals['rsi']}, MACD={signals['macd']}<{signals['macd_signal']}, Sentiment={signals['sentiment']}, OnChain={signals['onchain']}")
        self.position_open_time.pop(symbol, None)
        self.last_decision[symbol] = 'SELL'
        return 'SELL'

    # Take profit / stop loss based on ATR bands
    latest_price = ohlcv[-1][4]  # Close price of last candle
    entry_price = settings.ENTRY_PRICE.get(symbol, latest_price)
    profit_target = entry_price * (1 + settings.TAKE_PROFIT_RATIO)
    stop_loss = entry_price * (1 - settings.STOP_LOSS_RATIO)

    if latest_price >= profit_target:
        logger.info(f"TP SELL for {symbol}: price {latest_price} >= target {profit_target}")
        self.position_open_time.pop(symbol, None)
        self.last_decision[symbol] = 'SELL'
        return 'SELL'
    if latest_price <= stop_loss:
        logger.info(f"SL SELL for {symbol}: price {latest_price} <= stop {stop_loss}")
        self.position_open_time.pop(symbol, None)
        self.last_decision[symbol] = 'SELL'
        return 'SELL'

    # Otherwise hold
    self.last_decision[symbol] = 'HOLD'
    return 'HOLD'

def execute(self, executor):
    """
    Iterate through symbols and execute decisions via executor.
    """
    symbols = settings.SYMBOLS
    for symbol in symbols:
        action = self.decide(symbol)
        if action == 'BUY':
            executor.buy(symbol, settings.TRADE_USDT_AMOUNT)
        elif action == 'SELL':
            executor.sell(symbol)
        # HOLD does nothing


import random
from datetime import datetime, timedelta

from config import settings
from modules.time_strategy import get_current_strategy_mode
from core.logger import BotLogger
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity
from modules.technical_analysis import (
    fetch_ohlcv_from_binance,
    calculate_rsi,
    calculate_macd,
    calculate_atr
)

logger = BotLogger()

class Strategy:
    """
    Decision engine combining multi-timeframe technicals, sentiment & on-chain signals,
    regime detection via time strategy, and dynamic risk management for fully autonomous trading.
    Supports BUY, SELL, HOLD decisions with minimum hold time and optional TP/SL enforcement.
    """
    MIN_HOLD_TIME = timedelta(minutes=5)

    def __init__(self):
        # Track open positions and entry prices
        self.position_open_time = {}       # {symbol: datetime_opened}
        self.entry_prices = {}             # {symbol: entry_price}
        self.last_decision = {}            # {symbol: last_action}

    def reset(self):
        # Reset only last decisions
        self.last_decision.clear()

    def _get_signals(self, symbol):
        """
        Fetch market data and compute technical, sentiment, on-chain signals, plus last price.
        """
        # 1. Fetch OHLCV data
        ohlcv = fetch_ohlcv_from_binance(
            symbol,
            interval=getattr(settings, 'CANDLE_INTERVAL', '1m'),
            limit=getattr(settings, 'CANDLE_LIMIT', 50)
        )
        if not ohlcv:
            raise RuntimeError(f"No OHLCV data for {symbol}")

        # Extract last close price
        latest_price = ohlcv[-1][4]

        # 2. Compute technical indicators
        rsi = calculate_rsi([c[4] for c in ohlcv])[-1]
        macd, macd_signal, _ = calculate_macd([c[4] for c in ohlcv])
        atr = calculate_atr(ohlcv)

        # 3. Sentiment score
        sentiment_score = analyze_sentiment(symbol)

        # 4. On-chain activity
        whale_activity = track_onchain_activity(symbol)

        return {
            'price': latest_price,
            'rsi': rsi,
            'macd': macd[-1] if macd else 0,
            'macd_signal': macd_signal[-1] if macd_signal else 0,
            'atr': atr,
            'sentiment': sentiment_score,
            'onchain': whale_activity
        }

    def decide(self, symbol):
        """
        Decide action: BUY, HOLD, or SELL for the given symbol.
        """
        now = datetime.utcnow()
        signals = self._get_signals(symbol)
        price = signals['price']

        # Get current strategy mode if needed
        mode = get_current_strategy_mode()

        # No open position: evaluate BUY
        if symbol not in self.position_open_time:
            if (
                signals['rsi'] < settings.RSI_OVERSOLD and
                signals['sentiment'] > getattr(settings, 'SENTIMENT_THRESHOLD', 0)
            ):
                logger.info(f"Signal BUY for {symbol}: RSI={signals['rsi']}, Sentiment={signals['sentiment']}")
                self.position_open_time[symbol] = now
                self.entry_prices[symbol] = price
                self.last_decision[symbol] = 'BUY'
                return 'BUY'
            self.last_decision[symbol] = 'HOLD'
            return 'HOLD'

        # Position is open: enforce minimum hold time
        opened_at = self.position_open_time[symbol]
        if now - opened_at < self.MIN_HOLD_TIME:
            logger.info(f"HOLD {symbol}: min hold time not reached ({now - opened_at})")
            self.last_decision[symbol] = 'HOLD'
            return 'HOLD'

        # SELL conditions based on signals
        if (
            signals['rsi'] > settings.RSI_OVERBOUGHT or
            signals['macd'] < signals['macd_signal'] or
            signals['sentiment'] < -getattr(settings, 'SENTIMENT_THRESHOLD', 0) or
            signals['onchain'].get('large_sells', False)
        ):
            logger.info(
                f"Signal SELL for {symbol}: RSI={signals['rsi']}, "
                f"MACD={signals['macd']}<{signals['macd_signal']}, "
                f"Sentiment={signals['sentiment']}, OnChain={signals['onchain']}"
            )
            self.position_open_time.pop(symbol, None)
            self.entry_prices.pop(symbol, None)
            self.last_decision[symbol] = 'SELL'
            return 'SELL'

        # Optional: take-profit / stop-loss based on entry price
        entry_price = self.entry_prices.get(symbol, price)
        tp = entry_price * (1 + settings.TAKE_PROFIT_RATIO)
        sl = entry_price * (1 - settings.STOP_LOSS_RATIO)
        if price >= tp:
            logger.info(f"TP SELL for {symbol}: price {price} >= target {tp}")
            self.position_open_time.pop(symbol, None)
            self.entry_prices.pop(symbol, None)
            self.last_decision[symbol] = 'SELL'
            return 'SELL'
        if price <= sl:
            logger.info(f"SL SELL for {symbol}: price {price} <= stop {sl}")
            self.position_open_time.pop(symbol, None)
            self.entry_prices.pop(symbol, None)
            self.last_decision[symbol] = 'SELL'
            return 'SELL'

        # Otherwise HOLD
        self.last_decision[symbol] = 'HOLD'
        return 'HOLD'

    def execute(self, executor):
        """
        Iterate through symbols and execute decisions via executor.
        """
        for symbol in settings.SYMBOLS:
            action = self.decide(symbol)
            if action == 'BUY':
                executor.buy(symbol, settings.TRADE_USDT_AMOUNT)
            elif action == 'SELL':
                executor.sell(symbol)
            # HOLD does nothing

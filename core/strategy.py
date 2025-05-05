import random
from datetime import datetime, timedelta

from config import settings
from modules.time_strategy import get_current_strategy_mode
from core.logger import BotLogger
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity
from core.risk_manager import RiskManager

logger = BotLogger()

def calculate_sma(prices, period):
    """Simple moving average helper if not available in technical_analysis."""
    if not prices:
        return 0
    if len(prices) < period:
        return sum(prices) / len(prices)
    return sum(prices[-period:]) / period

class Strategy:
    """
    Decision engine with trend filters, technicals, sentiment/on-chain signals,
    dynamic risk sizing, SL/TP/OCO via RiskManager, and drawdown protection.
    """
    MIN_HOLD_TIME = timedelta(minutes=5)

    def __init__(self):
        self.position_open_time = {}
        self.reset()

    def reset(self):
        self.symbol = None
        self.mode = None
        self.risk = None
        self.pressure = None
        self.tech = {}
        self.sentiment = 0.0
        self.onchain = 0.0
        self.growth_factor = 1.0
        self.tp_ratio = settings.TAKE_PROFIT_RATIO
        self.sl_ratio = settings.STOP_LOSS_RATIO

    def update_context(
        self,
        symbol,
        mode,
        risk,
        pressure,
        rsi_15m=None,
        macd_15m=None,
        macd_signal_15m=None,
        rsi_1h=None,
        macd_1h=None,
        macd_signal_1h=None,
        atr=None,
        growth_factor=None,
        take_profit_ratio=None,
        stop_loss_ratio=None
    ):
        self.reset()
        self.symbol = symbol
        self.mode = mode
        self.risk = risk
        self.pressure = pressure
        self.tech = {
            'rsi_15m': rsi_15m,
            'macd_15m': macd_15m,
            'macd_signal_15m': macd_signal_15m,
            'rsi_1h': rsi_1h,
            'macd_1h': macd_1h,
            'macd_signal_1h': macd_signal_1h,
            'atr': atr
        }
        if growth_factor is not None:
            self.growth_factor = growth_factor
        if take_profit_ratio is not None:
            self.tp_ratio = take_profit_ratio
        if stop_loss_ratio is not None:
            self.sl_ratio = stop_loss_ratio
        # sentiment & on-chain
        try:
            self.sentiment = float(analyze_sentiment(symbol).get('score', 0))
        except:
            self.sentiment = 0.0
        try:
            self.onchain = float(track_onchain_activity(symbol).get('activity', 0))
        except:
            self.onchain = 0.0

    def decide_trade(self, current_balance, current_pnl):
        reason = []
        # Drawdown protection
        drawdown_pct = (settings.INITIAL_BALANCE and current_pnl / settings.INITIAL_BALANCE) or 0
        if drawdown_pct <= -settings.MAX_DRAWDOWN_PCT:
            reason.append('MaxDD')
            return {'action': 'HOLD', 'reason': '|'.join(reason)}

        # Fetch price series for trend and RSI
        try:
            ohlcv = fetch_ohlcv_from_binance(self.symbol, '15m', limit=60)
            prices = [c[4] for c in ohlcv]
        except Exception as e:
            logger.log(f"[STRATEGY] Price fetch error: {e}", level="ERROR")
            return {'action': 'HOLD', 'reason': 'NoData'}
        current_price = prices[-1]
        rsi_15m = calculate_rsi(prices)[-1]
        ma50 = calculate_sma(prices, 50)

        action = 'HOLD'
        # TP/SL based on pnl
        profit_pct = current_pnl / (settings.INITIAL_BALANCE or 1)
        if profit_pct >= self.tp_ratio:
            reason.append(f'TP{self.tp_ratio:.2f}')
            action = 'SELL'
        elif profit_pct <= -self.sl_ratio:
            reason.append(f'SL{self.sl_ratio:.2f}')
            action = 'SELL'

        # Enforce minimum hold time
        if action == 'SELL' and self.symbol in self.position_open_time:
            opened = self.position_open_time[self.symbol]
            if datetime.utcnow() - opened < self.MIN_HOLD_TIME:
                reason.append('MinHold')
                return {'action': 'HOLD', 'reason': '|'.join(reason)}
            self.position_open_time.pop(self.symbol, None)
            return {'action': 'SELL', 'reason': '|'.join(reason)}

        # Risk-off conditions
        if self.mode in ['holiday', 'macro_event'] or self.risk == 'extreme_risk':
            reason.append('RiskOff')
            return {'action': 'HOLD', 'reason': '|'.join(reason)}

        # Trend + RSI filters
        if action == 'HOLD':
            if rsi_15m < settings.RSI_OVERSOLD and current_price > ma50:
                action = 'BUY'
                reason.append('TrendBuy')
            elif rsi_15m > settings.RSI_OVERBOUGHT and current_price < ma50:
                action = 'SELL'
                reason.append('TrendSell')

        # Stealth drop
        if action in ['BUY','SELL'] and random.random() < settings.TRADE_DROP_CHANCE:
            reason.append('Jitter')
            action = 'HOLD'

        # Record open time
        if action == 'BUY' and self.symbol not in self.position_open_time:
            self.position_open_time[self.symbol] = datetime.utcnow()

        # Position sizing and risk manager for BUY
        if action == 'BUY':
            size_pct = settings.POSITION_SIZE_PCT * self.growth_factor
            rm = RiskManager(entry_price=current_price,
                             quantity=current_balance * size_pct,
                             sl_ratio=self.sl_ratio,
                             tp_ratio=self.tp_ratio,
                             trailing=settings.ATR_RATIO)
            rm.create_oco_order(self.symbol)
            return {
                'action': 'BUY',
                'reason': '|'.join(reason),
                'size_pct': size_pct
            }

        return {'action': action, 'reason': '|'.join(reason)}

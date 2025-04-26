import random
from datetime import datetime, timedelta

from config import settings
from modules.period_manager import get_current_period
from modules.time_strategy import get_current_strategy_mode
from modules.global_risk_index import GlobalRiskAnalyzer
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity
from core.logger import BotLogger

logger = BotLogger()

class Strategy:
    """
    Enhanced decision engine combining multi-timeframe technicals,
    sentiment & on-chain signals, regime detection via period targets,
    and dynamic risk management for fully autonomous trading.
    """
    MIN_HOLD_TIME = timedelta(minutes=5)

    def __init__(self):
        # Track when positions opened: {symbol: datetime}
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

    def update_context(self, symbol, mode, risk, pressure,
                       rsi_15m=None, macd_15m=None, macd_signal_15m=None,
                       rsi_1h=None, macd_1h=None, macd_signal_1h=None,
                       atr=None):
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
        # Normalize sentiment
        raw_sent = analyze_sentiment(symbol)
        try:
            self.sentiment = float(raw_sent.get('score', raw_sent) if isinstance(raw_sent, dict) else raw_sent)
        except (ValueError, TypeError):
            self.sentiment = 0.0
        # Normalize on-chain
        raw_chain = track_onchain_activity(symbol)
        try:
            self.onchain = float(raw_chain.get('activity', raw_chain) if isinstance(raw_chain, dict) else raw_chain)
        except (ValueError, TypeError):
            self.onchain = 0.0

    def decide_trade(self, current_balance, current_pnl):
        """
        Decide BUY/SELL/HOLD based on composite score, period-specific
        profit/stop thresholds, and dynamic position sizing.
        Returns dict with keys: action, reason, size_pct.
        """
        # Get current period configuration
        period = get_current_period() or {}
        # Dynamic ratios and growth factor
        tp_ratio = period.get('take_profit_ratio', settings.TAKE_PROFIT_RATIO)
        sl_ratio = period.get('stop_loss_ratio', settings.STOP_LOSS_RATIO)
        growth_factor = period.get('growth_factor', 1.0)

        reason = []
        score = 0.0
        # Position size scales by period growth factor
        base_pct = settings.POSITION_SIZE_PCT
        size_pct = round(base_pct * growth_factor, 4)
        reason.append(f"Growth{x:g}".replace('x', str(growth_factor)))

        # Profit-target or stop-loss exit
        profit_pct = current_pnl / (settings.INITIAL_BALANCE or 1)
        action = None
        if profit_pct >= tp_ratio:
            reason.append(f'TP({tp_ratio:.2f})')
            action = 'SELL'
        elif profit_pct <= -sl_ratio:
            reason.append(f'SL({sl_ratio:.2f})')
            action = 'SELL'

        # Minimum hold time enforcement before sell
        if action == 'SELL' and self.symbol in self.position_open_time:
            opened = self.position_open_time[self.symbol]
            if datetime.utcnow() - opened < self.MIN_HOLD_TIME:
                reason.append('MinHold')
                return {'action': 'HOLD', 'reason': '|'.join(reason), 'size_pct': 0.0}
            # Clear open time and return sell
            self.position_open_time.pop(self.symbol, None)
            return {'action': 'SELL', 'reason': '|'.join(reason), 'size_pct': 0.0}

        # Mode & risk checks
        if self.mode in ['holiday', 'macro_event'] or self.risk == 'extreme_risk':
            reason.append('NoTrade')
            return {'action': 'HOLD', 'reason': '|'.join(reason), 'size_pct': 0.0}

        # Liquidity pressure impact
        if self.pressure == 'buy_pressure':
            score += 0.5; reason.append('BuyPres')
        if self.pressure == 'sell_pressure':
            score -= 0.5; reason.append('SellPres')

        # Technical indicators
        r1 = self.tech.get('rsi_1h'); m1 = self.tech.get('macd_1h'); sig1 = self.tech.get('macd_signal_1h')
        if r1 is not None:
            if r1 < settings.RSI_OVERSOLD: score += 0.7; reason.append('RSI1hOS')
            elif r1 > settings.RSI_OVERBOUGHT: score -= 0.7; reason.append('RSI1hOB')
        if m1 is not None and sig1 is not None:
            score += 0.5 if m1 > sig1 else -0.5; reason.append('MACD1h')

        r15 = self.tech.get('rsi_15m'); m15 = self.tech.get('macd_15m'); sig15 = self.tech.get('macd_signal_15m')
        if r15 is not None:
            if r15 < settings.RSI_OVERSOLD: score += 0.3; reason.append('RSI15mOS')
            elif r15 > settings.RSI_OVERBOUGHT: score -= 0.3; reason.append('RSI15mOB')
        if m15 is not None and sig15 is not None:
            score += 0.3 if m15 > sig15 else -0.3; reason.append('MACD15m')

        # Sentiment & on-chain contributions
        score += self.sentiment * 0.2; reason.append('Sentiment')
        score += self.onchain * 0.2; reason.append('OnChain')

        # Volatility scaling
        atr = self.tech.get('atr')
        if atr is not None and atr < settings.ATR_MIN_VOL:
            score *= 0.5; reason.append('LowVol')

        # Final scoring
        thr = settings.SCORE_BUY_THRESHOLD
        if score >= thr:
            action = 'BUY'
        elif score <= -thr:
            action = 'SELL'
        else:
            action = 'HOLD'

        # Stealth jitter: occasional hold instead of action
        if action in ['BUY','SELL'] and random.random() < settings.TRADE_DROP_CHANCE:
            reason.append('JitterDrop')
            action = 'HOLD'

        # Track buy open time
        if action == 'BUY':
            self.position_open_time[self.symbol] = datetime.utcnow()
        elif action == 'SELL':
            self.position_open_time.pop(self.symbol, None)

        return {'action': action, 'reason': '|'.join(reason), 'size_pct': size_pct}

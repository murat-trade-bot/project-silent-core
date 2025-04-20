import random
import time

from config import settings
from modules.time_strategy import get_current_strategy_mode
from modules.global_risk_index import GlobalRiskAnalyzer
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity

class Strategy:
    """
    Decision engine combining technical indicators, sentiment, on-chain data,
    risk levels, and phased targets to generate BUY/SELL/HOLD signals.
    Ensures no leveraged positions and stealthy behavior.
    """
    def __init__(self):
        # Context variables
        self.reset_context()
        # Load phase targets from settings (list of cumulative USDT targets)
        self.phase_targets = settings.PHASE_TARGETS  # e.g., [1000, 5000,...]

    def reset_context(self):
        self.mode = None
        self.risk = None
        self.pressure = None
        self.tech = {}
        self.sentiment_score = 0.0
        self.onchain_activity = 0.0

    def update_context(self, symbol, mode, risk, pressure,
                       rsi_15m=None, macd_15m=None, macd_signal_15m=None,
                       rsi_1h=None, macd_1h=None, macd_signal_1h=None,
                       atr=None):
        self.reset_context()
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
        # Sentiment and onchain signals
        self.sentiment_score = analyze_sentiment(symbol)
        self.onchain_activity = track_onchain_activity(symbol)

    def decide_trade(self, balance_usdt, current_pnl):
        """
        Calculate a composite score and decide action.
        balance_usdt: current USDT balance
        current_pnl: current profit/loss relative to start
        returns dict with action, reason, and size_pct
        """
        reasons = []
        score = 0.0
        # Phase-based position sizing
        phase_index = next((i for i, target in enumerate(self.phase_targets) if current_pnl < target), len(self.phase_targets)-1)
        size_pct = settings.POSITION_SIZE_PCT * (1 + phase_index*0.1)
        reasons.append(f"Phase{phase_index+1}")

        # Time strategy mode: avoid trading on high-impact events
        if self.mode in ['holiday', 'macro_event']:
            reasons.append('NoTrade-Mode')
            return {'action': 'HOLD', 'reason': '|'.join(reasons), 'size_pct': 0.0}

        # Extreme risk protection
        if self.risk == 'extreme_risk':
            reasons.append('RiskStop')
            return {'action': 'HOLD', 'reason': '|'.join(reasons), 'size_pct': 0.0}

        # Liquidity pressure influences
        if self.pressure == 'buy_pressure':
            score += 0.5; reasons.append('BuyPressure')
        elif self.pressure == 'sell_pressure':
            score -= 0.5; reasons.append('SellPressure')

        # Technical indicators: momentum and oversold
        r1 = self.tech.get('rsi_1h')
        if r1 is not None:
            if r1 < settings.RSI_OVERSOLD: score += 0.7; reasons.append('RSI1hOversold')
            elif r1 > settings.RSI_OVERBOUGHT: score -= 0.7; reasons.append('RSI1hOB')
        m1 = self.tech.get('macd_1h')
        s1 = self.tech.get('macd_signal_1h')
        if m1 is not None and s1 is not None:
            if m1 > s1: score += 0.5; reasons.append('MACD1hUp')
            else: score -= 0.5; reasons.append('MACD1hDown')
        # Shorter timeframe confirmation
        r15 = self.tech.get('rsi_15m')
        if r15 is not None:
            if r15 < settings.RSI_OVERSOLD: score += 0.3; reasons.append('RSI15mOS')
            elif r15 > settings.RSI_OVERBOUGHT: score -= 0.3; reasons.append('RSI15m OB')

        # Sentiment and onchain add/subtract
        score += self.sentiment_score*0.2; reasons.append('Sentiment')
        score += self.onchain_activity*0.2; reasons.append('OnChain')

        # Volatility check: avoid choppy markets
        atr = self.tech.get('atr')
        if atr is not None and atr < settings.ATR_MIN_VOL:
            score *= 0.5; reasons.append('LowVol')

        # Final decision thresholds
        if score >= settings.SCORE_BUY_THRESHOLD:
            action = 'BUY'
        elif score <= -settings.SCORE_BUY_THRESHOLD:
            action = 'SELL'
        else:
            action = 'HOLD'

        # Introduce jitter: occasionally skip to avoid pattern
        if action != 'HOLD' and random.random() < settings.TRADE_DROP_CHANCE:
            reasons.append('JitterDrop')
            action = 'HOLD'

        return {'action': action, 'reason': '|'.join(reasons), 'size_pct': round(size_pct,4)}

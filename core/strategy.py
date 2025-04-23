import random
from datetime import datetime, timedelta

from config import settings
from modules.time_strategy import get_current_strategy_mode
from modules.global_risk_index import GlobalRiskAnalyzer
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity
from core.logger import BotLogger

logger = BotLogger()

class Strategy:
    """
    Enhanced decision engine combining multi-timeframe technicals,
    sentiment & on-chain signals, regime detection, period targets,
    and dynamic risk management for fully autonomous trading.
    """
    def __init__(self):
        # Load period targets and compute schedule
        self.period_targets = settings.PHASE_TARGETS
        self.period_start_balance = settings.INITIAL_BALANCE
        self.current_period = 0
        self.period_start_time = datetime.utcnow()
        # Reset context
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
        # External signals
        self.sentiment = analyze_sentiment(symbol)
        self.onchain = track_onchain_activity(symbol)

    def _check_period(self, current_balance):
        # Advance period if target reached or time elapsed (2 months each)
        target = self.period_targets[self.current_period]
        if current_balance >= target:
            self.current_period = min(self.current_period + 1, len(self.period_targets)-1)
            self.period_start_balance = current_balance
            self.period_start_time = datetime.utcnow()
        # Time-based check: assume each period ~60 days
        if datetime.utcnow() - self.period_start_time >= timedelta(days=60):
            self.current_period = min(self.current_period + 1, len(self.period_targets)-1)
            self.period_start_balance = current_balance
            self.period_start_time = datetime.utcnow()

    def decide_trade(self, current_balance, current_pnl):
        """
        Decide BUY/SELL/HOLD based on composite score and dynamic period goals.
        Returns dict with action, reason, size_pct.
        """
        # Period management
        self._check_period(current_balance)
        reason = []
        score = 0.0
        # Position size scales with period (more aggressive if behind)
        base_pct = settings.POSITION_SIZE_PCT
        size_pct = base_pct * (1 + self.current_period * 0.1)
        reason.append(f"Period{self.current_period+1}")

        # Mode & risk checks
        if self.mode in ['holiday','macro_event']:
            reason.append('NoTrade-Mode')
            return {'action':'HOLD','reason':'|'.join(reason),'size_pct':0.0}
        if self.risk == 'extreme_risk':
            reason.append('RiskStop')
            return {'action':'HOLD','reason':'|'.join(reason),'size_pct':0.0}

        # Liquidity
        if self.pressure=='buy_pressure': score+=0.5; reason.append('BuyPres')
        if self.pressure=='sell_pressure': score-=0.5; reason.append('SellPres')

        # Technical signals
        r1=self.tech['rsi_1h']; rsig1=self.tech['macd_signal_1h']; m1=self.tech['macd_1h']
        if r1 is not None:
            if r1<settings.RSI_OVERSOLD: score+=0.7; reason.append('RSI1hOS')
            elif r1>settings.RSI_OVERBOUGHT: score-=0.7; reason.append('RSI1hOB')
        if m1 is not None and rsig1 is not None:
            if m1>rsig1: score+=0.5; reason.append('MACD1hUp')
            else: score-=0.5; reason.append('MACD1hDown')
        r15=self.tech['rsi_15m']; rsig15=self.tech['macd_signal_15m']; m15=self.tech['macd_15m']
        if r15 is not None:
            if r15<settings.RSI_OVERSOLD: score+=0.3; reason.append('RSI15mOS')
            elif r15>settings.RSI_OVERBOUGHT: score-=0.3; reason.append('RSI15mOB')
        if m15 is not None and rsig15 is not None:
            if m15>rsig15: score+=0.3; reason.append('MACD15mUp')
            else: score-=0.3; reason.append('MACD15mDown')

        # Sentiment & on-chain
        score+=self.sentiment*0.2; reason.append('Sentiment')
        score+=self.onchain*0.2; reason.append('OnChain')

        # Volatility
        atr=self.tech['atr']
        if atr is not None and atr<settings.ATR_MIN_VOL: score*=0.5; reason.append('LowVol')

        # Final thresholds
        thr=settings.SCORE_BUY_THRESHOLD
        if score>=thr: action='BUY'
        elif score<=-thr: action='SELL'
        else: action='HOLD'

        # Stealth jitter drop small trades occasionally
        if action!='HOLD' and random.random()<settings.TRADE_DROP_CHANCE:
            reason.append('JitterDrop')
            action='HOLD'

        return {'action':action,'reason':'|'.join(reason),'size_pct':round(size_pct,4)}

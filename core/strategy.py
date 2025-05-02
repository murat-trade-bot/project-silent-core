# core/strategy.py

import random
from datetime import datetime, timedelta

from config import settings
from modules.time_strategy import get_current_strategy_mode
from core.logger import BotLogger
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity

logger = BotLogger()

class Strategy:
    """
    Enhanced decision engine combining multi-timeframe technicals,
    sentiment & on-chain signals, regime detection via period targets,
    and dynamic risk management for fully autonomous trading.
    """
    MIN_HOLD_TIME = timedelta(minutes=5)

    def __init__(self):
        # Pozisyon açılma zamanlarını tutar (symbol → datetime)
        self.position_open_time = {}
        # Context ve dönem parametrelerini hazırla
        self.reset()

    def reset(self):
        # Sadece context bilgisini sıfırlar (pozisyon zamanları korunur)
        self.symbol = None
        self.mode = None
        self.risk = None
        self.pressure = None

        # Teknik analiz sinyalleri
        self.tech = {
            'rsi_15m': None,
            'macd_15m': None,
            'macd_signal_15m': None,
            'rsi_1h': None,
            'macd_1h': None,
            'macd_signal_1h': None,
            'atr': None
        }

        # Duygu ve on-chain
        self.sentiment = 0.0
        self.onchain = 0.0

        # Dönem parametreleri (ana ayarlardan gelen varsayılanlar)
        self.growth_factor = 1.0                   # main.py'den gelen growth_factor
        self.tp_ratio      = settings.TAKE_PROFIT_RATIO  # main.py'den gelen tp_ratio
        self.sl_ratio      = settings.STOP_LOSS_RATIO    # main.py'den gelen sl_ratio

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
        growth_factor=None,    # ← main.py: update_settings_for_period()["growth_factor"]
        tp_ratio=None,         # ← main.py: update_settings_for_period()["take_profit_ratio"]
        sl_ratio=None          # ← main.py: update_settings_for_period()["stop_loss_ratio"]
    ):
        # Context bilgisini temizle (pozisyon zamanları harici)
        self.reset()

        # Temel context
        self.symbol = symbol
        self.mode   = mode
        self.risk   = risk
        self.pressure = pressure

        # Teknik sinyalleri ata
        self.tech.update({
            'rsi_15m': rsi_15m,
            'macd_15m': macd_15m,
            'macd_signal_15m': macd_signal_15m,
            'rsi_1h': rsi_1h,
            'macd_1h': macd_1h,
            'macd_signal_1h': macd_signal_1h,
            'atr': atr
        })

        # Dönemden gelen parametreleri uygula
        if growth_factor is not None:
            self.growth_factor = growth_factor
        if tp_ratio is not None:
            self.tp_ratio = tp_ratio
        if sl_ratio is not None:
            self.sl_ratio = sl_ratio

        # Sentiment analizi
        raw_sent = analyze_sentiment(symbol)
        try:
            self.sentiment = float(
                raw_sent.get('score', raw_sent)
                if isinstance(raw_sent, dict) else raw_sent
            )
        except:
            self.sentiment = 0.0

        # On-chain aktivite
        raw_chain = track_onchain_activity(symbol)
        try:
            self.onchain = float(
                raw_chain.get('activity', raw_chain)
                if isinstance(raw_chain, dict) else raw_chain
            )
        except:
            self.onchain = 0.0

    def decide_trade(self, current_balance, current_pnl):
        reason = []
        score = 0.0

        # Pozisyon büyüklüğü: main.py'den gelen growth_factor ile çarpılıyor
        size_pct = round(settings.POSITION_SIZE_PCT * self.growth_factor, 4)
        reason.append(f"Growth{self.growth_factor:g}")

        # Kar/Zarar kontrolü: dönemden gelen tp_ratio / sl_ratio
        profit_pct = current_pnl / (settings.INITIAL_BALANCE or 1)
        action = None
        if profit_pct >= self.tp_ratio:
            reason.append(f"TP({self.tp_ratio:.2f})")
            action = 'SELL'
        elif profit_pct <= -self.sl_ratio:
            reason.append(f"SL({self.sl_ratio:.2f})")
            action = 'SELL'

        # Minimum hold time kontrolü
        if action == 'SELL' and self.symbol in self.position_open_time:
            opened = self.position_open_time[self.symbol]
            if datetime.utcnow() - opened < self.MIN_HOLD_TIME:
                reason.append('MinHold')
                return {'action': 'HOLD', 'reason': '|'.join(reason), 'size_pct': 0.0}
            self.position_open_time.pop(self.symbol, None)
            return {'action': 'SELL', 'reason': '|'.join(reason), 'size_pct': 0.0}

        # Risk modu veya özel zamanlar
        if self.mode in ['holiday', 'macro_event'] or self.risk == 'extreme_risk':
            reason.append('NoTrade')
            return {'action': 'HOLD', 'reason': '|'.join(reason), 'size_pct': 0.0}

        # Liquidity pressure
        if self.pressure == 'buy_pressure':
            score += 0.5; reason.append('BuyPres')
        if self.pressure == 'sell_pressure':
            score -= 0.5; reason.append('SellPres')

        # Teknik indikatörler (1h ve 15m)
        r1, m1, s1 = self.tech['rsi_1h'], self.tech['macd_1h'], self.tech['macd_signal_1h']
        if r1 is not None:
            if r1 < settings.RSI_OVERSOLD:    score += 0.7; reason.append('RSI1hOS')
            elif r1 > settings.RSI_OVERBOUGHT: score -= 0.7; reason.append('RSI1hOB')
        if m1 is not None and s1 is not None:
            score += (0.5 if m1 > s1 else -0.5); reason.append('MACD1h')

        r15, m15, s15 = self.tech['rsi_15m'], self.tech['macd_15m'], self.tech['macd_signal_15m']
        if r15 is not None:
            if r15 < settings.RSI_OVERSOLD:    score += 0.3; reason.append('RSI15mOS')
            elif r15 > settings.RSI_OVERBOUGHT: score -= 0.3; reason.append('RSI15mOB')
        if m15 is not None and s15 is not None:
            score += (0.3 if m15 > s15 else -0.3); reason.append('MACD15m')

        # Sentiment & On-chain katkısı
        score += self.sentiment * 0.2; reason.append('Sentiment')
        score += self.onchain   * 0.2; reason.append('OnChain')

        # ATR bazlı volatilite scaling
        atr = self.tech['atr']
        if atr is not None and atr < settings.ATR_MIN_VOL:
            score *= 0.5; reason.append('LowVol')

        # Nihai karar
        if action is None:
            thr = settings.SCORE_BUY_THRESHOLD
            if score >= thr:
                action = 'BUY'
            elif score <= -thr:
                action = 'SELL'
            else:
                action = 'HOLD'

        # Stealth jitter
        if action in ['BUY','SELL'] and random.random() < settings.TRADE_DROP_CHANCE:
            reason.append('JitterDrop')
            action = 'HOLD'

        # Pozisyon açıldıysa kaydet, kapatıldıysa sil
        if action == 'BUY' and self.symbol not in self.position_open_time:
            self.position_open_time[self.symbol] = datetime.utcnow()
        elif action == 'SELL' and self.symbol in self.position_open_time:
            self.position_open_time.pop(self.symbol, None)

        return {'action': action, 'reason': '|'.join(reason), 'size_pct': size_pct}

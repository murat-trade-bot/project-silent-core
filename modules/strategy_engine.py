"""
Strategy Engine Module
Tüm analiz modüllerinden gelen verileri birleştirir, işlem sinyali ve pozisyon kararı üretir.
Stealth mod, risk yönetimi ve 6 dönemlik kazanç planı ile tam uyumludur.
"""

from modules.technical_analysis import calculate_rsi, calculate_macd
from modules.sentiment_analysis import SentimentAnalysis
from modules.global_risk_index import GlobalRiskAnalyzer
from modules.dynamic_position import DynamicPosition
from core.logger import BotLogger
from config import settings

logger = BotLogger()

class StrategyEngine:
    def __init__(self):
        self.sentiment = SentimentAnalysis()
        self.risk = GlobalRiskAnalyzer()
        self.position = DynamicPosition()
        self.period_multiplier = 1.0  # Dönem katsayısı, period_manager'dan alınabilir

    def analyze(self, prices, ohlcv, symbol="BTCUSDT"):
        # Teknik analiz
        rsi = calculate_rsi(prices)
        macd, signal = calculate_macd(prices)
        # Sentiment
        sentiment_score = self.sentiment.get_overall_sentiment(symbol)
        # Global risk
        risk_score = self.risk.composite_risk_score(self.period_multiplier)

        logger.info(f"StrategyEngine: RSI={rsi[-1] if rsi else None}, MACD={macd[-1] if macd else None}, Sentiment={sentiment_score}, Risk={risk_score}")

        # Basit örnek karar mantığı
        if (rsi and rsi[-1] < 30 and sentiment_score > 0 and risk_score < 50):
            return "BUY"
        elif (rsi and rsi[-1] > 70 and sentiment_score < 0 and risk_score > 70):
            return "SELL"
        else:
            return "HOLD"

    def get_position_size(self, balance, stop_loss_pct, volatility):
        return self.position.calculate_position_size(balance, stop_loss_pct, volatility, self.period_multiplier)
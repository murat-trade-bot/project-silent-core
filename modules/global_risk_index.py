import requests
import random
import time
from core.logger import BotLogger
from config import settings
from modules.global_risk_index import GlobalRiskAnalyzer

logger = BotLogger()

class GlobalRiskAnalyzer:
    def __init__(self):
        self.fng_url = "https://api.alternative.me/fng/"
        # Makro ve jeopolitik risk için gerçek API anahtarlarını settings üzerinden al
        self.macro_api_key = getattr(settings, "TRADINGECONOMICS_API_KEY", None)
        self.geo_api_key = getattr(settings, "NEWS_API_KEY", None)
        self.macro_url = f"https://api.tradingeconomics.com/markets/indicators?c={self.macro_api_key}" if self.macro_api_key else None
        self.geo_url = f"https://newsapi.org/v2/top-headlines?category=world&apiKey={self.geo_api_key}" if self.geo_api_key else None
        self.global_risk = GlobalRiskAnalyzer()

    def fetch_fear_index(self) -> int:
        """
        Crypto Fear & Greed Index'i çeker. Stealth modda, hata toleranslı.
        """
        try:
            time.sleep(random.uniform(0.3, 1.2))  # Stealth: insanvari gecikme
            r = requests.get(self.fng_url, timeout=5)
            r.raise_for_status()
            data = r.json()
            value = int(data["data"][0]["value"])
            logger.info(f"GlobalRiskAnalyzer: Fear&Greed Index {value}")
            return value
        except Exception as e:
            logger.error(f"GlobalRiskAnalyzer: Fear&Greed fetch error: {e}")
            return 50  # Fail-safe: nötr skor

    def fetch_macro_risk(self) -> float:
        """
        Makroekonomik risk göstergesi (ör: ABD faiz oranı, enflasyon, VIX) çeker.
        Gerçek API ile entegre, fail durumunda dummy.
        """
        if not self.macro_url:
            logger.warning("Makro risk API anahtarı yok, dummy veri kullanılacak.")
            return random.uniform(4.5, 5.5)
        try:
            time.sleep(random.uniform(0.2, 0.8))
            r = requests.get(self.macro_url, timeout=7)
            r.raise_for_status()
            data = r.json()
            # Örnek: ABD faiz oranı veya VIX endeksi çekilebilir
            fed_rate = None
            for item in data:
                if "United States" in item.get("Country", "") and "Interest Rate" in item.get("Category", ""):
                    fed_rate = float(item.get("Value", 5.0))
                    break
            if fed_rate is None:
                fed_rate = random.uniform(4.5, 5.5)
            logger.info(f"GlobalRiskAnalyzer: FED rate {fed_rate:.2f}")
            return fed_rate
        except Exception as e:
            logger.error(f"GlobalRiskAnalyzer: Macro risk fetch error: {e}")
            return random.uniform(4.5, 5.5)

    def fetch_geopolitical_risk(self) -> float:
        """
        Jeopolitik risk göstergesi (haber başlıklarından sentiment skoru).
        """
        if not self.geo_url:
            logger.warning("Jeopolitik risk API anahtarı yok, dummy veri kullanılacak.")
            return random.uniform(0, 1)
        try:
            time.sleep(random.uniform(0.2, 0.8))
            r = requests.get(self.geo_url, timeout=7)
            r.raise_for_status()
            articles = r.json().get("articles", [])
            pos_words = ["peace", "deal", "agreement", "stable", "growth"]
            neg_words = ["war", "conflict", "attack", "sanction", "crisis"]
            score = 0
            for article in articles:
                title = article.get("title", "").lower()
                score += sum(word in title for word in pos_words)
                score -= sum(word in title for word in neg_words)
            norm_score = 0.5 + (score / max(len(articles), 1)) / 4  # -0.5...+0.5 arası normalize, 0.5 nötr
            norm_score = max(0, min(1, norm_score))
            logger.info(f"GlobalRiskAnalyzer: Geopolitical risk score {norm_score:.2f}")
            return norm_score
        except Exception as e:
            logger.error(f"GlobalRiskAnalyzer: Geopolitical risk fetch error: {e}")
            return 0.5

    def evaluate_risk_level(self, period_multiplier: float = 1.0) -> str:
        """
        Fear&Greed, makro ve jeopolitik risk skoruna göre risk seviyesi döndürür.
        Dönemsel hedef katsayısı ile uyumlu.
        """
        fear = self.fetch_fear_index()
        macro = self.fetch_macro_risk()
        geo = self.fetch_geopolitical_risk()
        # Kompozit risk: düşük fear, yüksek faiz, yüksek jeopolitik risk = yüksek risk
        risk_score = (100 - fear) * 0.5 + (macro - 4.5) * 20 * 0.3 + geo * 100 * 0.2
        risk_score *= period_multiplier
        if risk_score > 75:
            return "extreme_risk"
        elif risk_score > 50:
            return "high_risk"
        elif risk_score > 25:
            return "moderate"
        else:
            return "low_risk"

    def composite_risk_score(self, period_multiplier: float = 1.0) -> float:
        """
        Dönemsel hedef ve risk katsayısı ile uyumlu, normalize edilmiş risk skoru üretir.
        """
        fear = self.fetch_fear_index()
        macro = self.fetch_macro_risk()
        geo = self.fetch_geopolitical_risk()
        score = (100 - fear) * 0.5 + (macro - 4.5) * 20 * 0.3 + geo * 100 * 0.2
        score *= period_multiplier
        score = max(0, min(100, score))
        logger.info(f"GlobalRiskAnalyzer: Composite risk score {score:.2f}")
        return score

    # Kullanım:
    risk_level = self.global_risk.evaluate_risk_level()
    risk_score = self.global_risk.composite_risk_score()
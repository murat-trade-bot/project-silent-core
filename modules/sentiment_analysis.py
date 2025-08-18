"""
Sentiment Analysis Module 
Sadece Twitter ve NewsAPI ile çalışır.
"""

import requests
import random
import time
from typing import Optional
from core.logger import BotLogger

logger = BotLogger()


from typing import Any

class SentimentAnalysis:
    def __init__(self, twitter_bearer: str = None, news_api_key: str = None, delay_range: tuple = (0.5, 2.0)):
        """
        SentimentAnalysis modülü. API anahtarları parametre olarak alınabilir (test için kolaylık sağlar).
        delay_range: (min, max) gecikme aralığı (insanvari davranış için)
        """
        try:
            from config import settings
            self.twitter_bearer = twitter_bearer or getattr(settings, "TWITTER_BEARER_TOKEN", None) or getattr(settings, "TWITTER_API_KEY", None)
            self.news_api_key = news_api_key or getattr(settings, "NEWS_API_KEY", None)
            stealth = getattr(settings, "STEALTH_SLEEP_MIN", 0), getattr(settings, "STEALTH_SLEEP_MAX", 2)
            self.delay_range = delay_range if delay_range else stealth
        except Exception as e:
            logger.error(f"SentimentAnalysis init error: {e}")
            self.twitter_bearer = None
            self.news_api_key = None
            self.delay_range = (0.5, 2.0)

    def fetch_twitter_sentiment(self, query: str = "bitcoin") -> Optional[float]:
        """
        Twitter sentiment skorunu döndürür. API anahtarı yoksa veya hata olursa None döner.
        """
        if not self.twitter_bearer:
            logger.info("Twitter API anahtarı yok, twitter sentiment atlanıyor.")
            return None
        url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10"
        headers = {
            "Authorization": f"Bearer {self.twitter_bearer}",
            "User-Agent": f"Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourproject)"
        }
        try:
            time.sleep(random.uniform(*self.delay_range))
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 429:
                logger.warning("Twitter rate limit aşıldı (429). Twitter sentiment atlanıyor.")
                return None
            resp.raise_for_status()
            tweets = resp.json().get("data", [])
            pos_words = ["bull", "moon", "pump", "profit", "win"]
            neg_words = ["bear", "dump", "loss", "crash", "rekt"]
            score = 0
            for tweet in tweets:
                text = tweet.get("text", "").lower()
                score += sum(word in text for word in pos_words)
                score -= sum(word in text for word in neg_words)
            logger.info(f"Twitter sentiment score: {score}")
            return score / max(len(tweets), 1) if tweets else 0.0
        except Exception as e:
            logger.error(f"Twitter sentiment hatası: {e}")
            return None

    def fetch_news_sentiment(self, query: str = "bitcoin") -> Optional[float]:
        """
        NewsAPI üzerinden haber sentiment skorunu döndürür. API anahtarı yoksa veya hata olursa None döner.
        """
        if not self.news_api_key:
            logger.warning("News API anahtarı yok, sentiment atlanıyor.")
            return None
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&pageSize=10&apiKey={self.news_api_key}"
        headers = {
            "User-Agent": f"Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourproject)"
        }
        try:
            time.sleep(random.uniform(*self.delay_range))
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 429:
                logger.warning("NewsAPI rate limit aşıldı (429). Kısa süre bekleniyor.")
                time.sleep(2)
                return None
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            pos_words = ["rally", "gain", "growth", "surge", "positive"]
            neg_words = ["fall", "loss", "decline", "crash", "negative"]
            score = 0
            for article in articles:
                title = article.get("title", "").lower()
                score += sum(word in title for word in pos_words)
                score -= sum(word in title for word in neg_words)
            logger.info(f"News sentiment score: {score}")
            return score / max(len(articles), 1) if articles else 0.0
        except Exception as e:
            logger.error(f"News sentiment fetch error: {e}")
            return None

    def get_overall_sentiment(self, query: str = "bitcoin", fallback: Any = 0.0) -> float:
        """
        Twitter ve haber skorlarının ortalamasını döndürür. Hiçbiri alınamazsa fallback (default: 0.0) döner.
        """
        twitter_score = self.fetch_twitter_sentiment(query)
        news_score = self.fetch_news_sentiment(query)
        scores = [s for s in [twitter_score, news_score] if s is not None]
        if not scores:
            logger.warning("Hiçbir sentiment skoru alınamadı, fallback döndürülüyor.")
            return fallback
        avg_score = sum(scores) / len(scores)
        logger.info(f"Overall sentiment score: {avg_score}")
        return avg_score

def analyze_sentiment(query: str = "bitcoin", fallback: Any = 0.0) -> float:
    """
    SentimentAnalysis sınıfını kullanarak genel sentiment skorunu döndürür.
    Test ve entegrasyon için fallback ve parametre geçişi destekler.
    """
    sa = SentimentAnalysis()
    return sa.get_overall_sentiment(query, fallback=fallback)

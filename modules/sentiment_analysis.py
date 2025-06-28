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

class SentimentAnalysis:
    def __init__(self):
        try:
            from config import settings
            self.twitter_bearer = getattr(settings, "TWITTER_BEARER_TOKEN", None)
            self.news_api_key = getattr(settings, "NEWS_API_KEY", None)
        except Exception:
            self.twitter_bearer = None
            self.news_api_key = None

    def fetch_twitter_sentiment(self, query: str = "bitcoin") -> Optional[float]:
        """Twitter sentiment - yoksa None döner"""
        if not self.twitter_bearer:
            logger.info("Twitter API anahtarı yok, twitter sentiment atlanıyor.")
            return None
        
        url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10"
        headers = {
            "Authorization": f"Bearer {self.twitter_bearer}",
            "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourproject)"
        }
        try:
            time.sleep(random.uniform(0.5, 2.0))
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
            return score / max(len(tweets), 1)
        except Exception as e:
            logger.warning(f"Twitter sentiment hatası: {e}")
            return None

    def fetch_news_sentiment(self, query: str = "bitcoin") -> Optional[float]:
        """News sentiment"""
        if not self.news_api_key:
            logger.warning("News API anahtarı yok, sentiment atlanıyor.")
            return None
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&pageSize=10&apiKey={self.news_api_key}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourproject)"
        }
        try:
            time.sleep(random.uniform(0.5, 2.0))
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
            return score / max(len(articles), 1)
        except Exception as e:
            logger.error(f"News sentiment fetch error: {e}")
            return None

    def get_overall_sentiment(self, query: str = "bitcoin") -> float:
        """Twitter ve haber skorlarının ortalaması"""
        twitter_score = self.fetch_twitter_sentiment(query)
        news_score = self.fetch_news_sentiment(query)
        scores = [s for s in [twitter_score, news_score] if s is not None]
        if not scores:
            logger.warning("Hiçbir sentiment skoru alınamadı, 0 döndürülüyor.")
            return 0.0
        avg_score = sum(scores) / len(scores)
        logger.info(f"Overall sentiment score: {avg_score}")
        return avg_score

def analyze_sentiment(query: str = "bitcoin") -> float:
    """SentimentAnalysis sınıfını kullanarak genel sentiment skorunu döndürür."""
    sa = SentimentAnalysis()
    return sa.get_overall_sentiment(query)

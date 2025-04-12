import requests
import json
import time
from datetime import datetime, timedelta
from core.logger import BotLogger
from anti_binance_tespit import anti_detection

logger = BotLogger()

class SentimentAnalyzer:
    def __init__(self):
        self.cache = {}
        self.cache_expiry = 3600  # 1 saat
        self.news_api_key = "YOUR_NEWS_API_KEY"  # NewsAPI anahtarı
        self.twitter_api_key = "YOUR_TWITTER_API_KEY"  # Twitter API anahtarı
        self.reddit_client_id = "YOUR_REDDIT_CLIENT_ID"
        self.reddit_client_secret = "YOUR_REDDIT_CLIENT_SECRET"
        
    def get_cached_sentiment(self, symbol):
        """Önbellekten duygu analizi sonucunu alır"""
        if symbol in self.cache:
            timestamp, value = self.cache[symbol]
            if datetime.now().timestamp() - timestamp < self.cache_expiry:
                return value
        return None
        
    def cache_sentiment(self, symbol, value):
        """Duygu analizi sonucunu önbelleğe alır"""
        self.cache[symbol] = (datetime.now().timestamp(), value)
        
    def get_news_sentiment(self, symbol):
        """Haber kaynaklarından duygu analizi yapar"""
        try:
            anti_detection.check_rate_limit()
            base_symbol = symbol.replace("USDT", "").replace("BTC", "")
            url = f"https://newsapi.org/v2/everything"
            params = {
                "q": f"{base_symbol} cryptocurrency",
                "apiKey": self.news_api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10
            }
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])
                if not articles:
                    return 50  # Nötr
                
                # Basit bir duygu analizi
                positive_keywords = ["bullish", "surge", "rise", "gain", "positive", "growth", "adoption"]
                negative_keywords = ["bearish", "crash", "drop", "fall", "negative", "decline", "ban"]
                
                sentiment_score = 50
                for article in articles:
                    title = article.get("title", "").lower()
                    description = article.get("description", "").lower()
                    content = f"{title} {description}"
                    
                    for keyword in positive_keywords:
                        if keyword in content:
                            sentiment_score += 5
                    for keyword in negative_keywords:
                        if keyword in content:
                            sentiment_score -= 5
                
                return max(0, min(100, sentiment_score))
            return 50  # Hata durumunda nötr
        except Exception as e:
            logger.log(f"[SENTIMENT] Haber analizi hatası: {e}")
            return 50
            
    def get_social_sentiment(self, symbol):
        """Sosyal medyadan duygu analizi yapar"""
        try:
            anti_detection.check_rate_limit()
            base_symbol = symbol.replace("USDT", "").replace("BTC", "")
            
            # Twitter API çağrısı (gerçek uygulamada Twitter API kullanılmalı)
            # Şimdilik simüle ediyoruz
            time.sleep(random.uniform(1, 3))
            twitter_score = random.randint(40, 60)
            
            # Reddit API çağrısı (gerçek uygulamada Reddit API kullanılmalı)
            # Şimdilik simüle ediyoruz
            time.sleep(random.uniform(1, 3))
            reddit_score = random.randint(40, 60)
            
            return (twitter_score + reddit_score) / 2
        except Exception as e:
            logger.log(f"[SENTIMENT] Sosyal medya analizi hatası: {e}")
            return 50
            
    def get_market_sentiment(self, symbol):
        """Piyasa verilerinden duygu analizi yapar"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/ticker/24hr"
            params = {"symbol": symbol}
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
            if response.status_code == 200:
                data = response.json()
                price_change_percent = float(data.get("priceChangePercent", 0))
                volume_change = float(data.get("volume", 0)) - float(data.get("weightedAvgPrice", 0))
                
                # Fiyat değişimi ve hacim değişimine göre skor hesapla
                sentiment_score = 50
                if price_change_percent > 0:
                    sentiment_score += min(25, price_change_percent)
                else:
                    sentiment_score += max(-25, price_change_percent)
                    
                if volume_change > 0:
                    sentiment_score += 10
                else:
                    sentiment_score -= 10
                    
                return max(0, min(100, sentiment_score))
            return 50
        except Exception as e:
            logger.log(f"[SENTIMENT] Piyasa analizi hatası: {e}")
            return 50
            
    def analyze_sentiment(self, symbol="BTCUSDT"):
        """Tüm kaynaklardan duygu analizi yapar"""
        # Önbellekten kontrol et
        cached_value = self.get_cached_sentiment(symbol)
        if cached_value is not None:
            return cached_value
            
        # Farklı kaynaklardan analiz yap
        news_score = self.get_news_sentiment(symbol)
        social_score = self.get_social_sentiment(symbol)
        market_score = self.get_market_sentiment(symbol)
        
        # Ağırlıklı ortalama hesapla
        weighted_score = (news_score * 0.3) + (social_score * 0.3) + (market_score * 0.4)
        
        # Önbelleğe al
        self.cache_sentiment(symbol, weighted_score)
        
        return weighted_score

# Global instance
sentiment_analyzer = SentimentAnalyzer()

def analyze_sentiment(symbol="BTCUSDT"):
    """Dışa açık fonksiyon"""
    return sentiment_analyzer.analyze_sentiment(symbol) 
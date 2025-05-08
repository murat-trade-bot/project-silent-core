"""
Module: sentiment_analysis.py
Fetches and computes sentiment from news, social media, and market data.
Includes caching, proxy handling, rate-limit avoidance, and robust error handling.
"""
import time
import random
from datetime import datetime
from typing import Optional

import requests

from core.logger import BotLogger
from config import settings
try:
    from anti_binance_tespit import anti_detection
except ImportError:
    # Test/smoke aşamasında sentiment analizine ihtiyaç yok
    def anti_detection(*args, **kwargs):
        return None

logger = BotLogger()

class SentimentAnalyzer:
    def __init__(self):
        self.cache = {}  # symbol -> (timestamp, score)
        self.cache_expiry = getattr(settings, 'SENTIMENT_CACHE_EXPIRY', 3600)
        self.news_api_key = settings.NEWS_API_KEY
        self.api_timeout = settings.API_TIMEOUT
        self.use_proxy = settings.USE_PROXY

    def _get_cached(self, symbol: str) -> Optional[float]:
        entry = self.cache.get(symbol)
        if entry:
            ts, val = entry
            if time.time() - ts < self.cache_expiry:
                return val
        return None

    def _set_cache(self, symbol: str, value: float):
        self.cache[symbol] = (time.time(), value)

    def _fetch(self, url: str, params: dict, headers: dict=None) -> Optional[dict]:
        try:
            anti_detection.check_rate_limit()
            proxies = anti_detection.get_next_proxy() if self.use_proxy else None
            resp = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=self.api_timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"[SENTIMENT] HTTP error: {e}")
        except ValueError as e:
            logger.error(f"[SENTIMENT] JSON parse error: {e}")
        return None

    def _news_score(self, symbol: str) -> float:
        if not self.news_api_key:
            return 50.0
        base = symbol.replace('USDT','')
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': f'{base} cryptocurrency',
            'apiKey': self.news_api_key,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 10
        }
        headers = {'User-Agent': anti_detection.get_random_user_agent()}
        data = self._fetch(url, params, headers)
        if not data or 'articles' not in data:
            return 50.0
        pos_kw = ["bullish","surge","rise","gain","positive","growth","adoption"]
        neg_kw = ["bearish","crash","drop","fall","negative","decline","ban"]
        score = 50.0
        for art in data['articles']:
            content = (art.get('title','') + ' ' + art.get('description','')).lower()
            for kw in pos_kw:
                if kw in content:
                    score += 5
            for kw in neg_kw:
                if kw in content:
                    score -= 5
        return max(0.0, min(100.0, score))

    def _social_score(self, symbol: str) -> float:
        try:
            anti_detection.check_rate_limit()
            # Placeholder: simulate Twitter/Reddit sentiment
            time.sleep(random.uniform(0.5,1.5))
            score = random.uniform(40,60)
            return score
        except Exception as e:
            logger.error(f"[SENTIMENT] social sentiment error: {e}")
            return 50.0

    def _market_score(self, symbol: str) -> float:
        url = 'https://api.binance.com/api/v3/ticker/24hr'
        params = {'symbol': symbol}
        data = self._fetch(url, params)
        if not data:
            return 50.0
        try:
            change_pct = float(data.get('priceChangePercent',0))
            vol = float(data.get('volume',0))
            avg_price = float(data.get('weightedAvgPrice',0))
            vol_change = vol - avg_price
            score = 50.0
            score += max(-25.0, min(25.0, change_pct))
            score += 10.0 if vol_change>0 else -10.0
            return max(0.0, min(100.0, score))
        except (ValueError, KeyError) as e:
            logger.error(f"[SENTIMENT] market sentiment parse error: {e}")
            return 50.0

    def analyze_sentiment(self, symbol: str='BTCUSDT') -> float:
        cached = self._get_cached(symbol)
        if cached is not None:
            return cached
        n = self._news_score(symbol)
        s = self._social_score(symbol)
        m = self._market_score(symbol)
        weighted = n*0.3 + s*0.3 + m*0.4
        weighted = max(0.0, min(100.0, weighted))
        self._set_cache(symbol, weighted)
        logger.info(f"[SENTIMENT] {symbol}: news={n:.1f}, social={s:.1f}, market={m:.1f} => {weighted:.1f}")
        return weighted

# Global function
analyze_sentiment = SentimentAnalyzer().analyze_sentiment

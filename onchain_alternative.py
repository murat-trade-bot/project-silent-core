"""
onchain_alternative.py

Spot trade bot için onchain benzeri analiz modülü.
- Binance API & Websocket ile order book, hacim, büyük işlemler, balina hareketi tahmini
- Twitter sentiment analizi (pump, dump, crash, panic, fud gibi anahtar kelimeler)
- CoinGecko veya Yahoo Finance ile makro veriler (marketcap, dominance, toplam arz)
- (Opsiyonel) Basit ML ile trend tahmini

Not: Bu modül, ücretli API kullanmaz ve kolayca genişletilebilir şekilde tasarlanmıştır.
"""

import time
import requests
import threading
import logging
from collections import deque
from datetime import datetime, timedelta
import random

# Twitter sentiment için
import re
import os
import tweepy
from textblob import TextBlob

# ML için (opsiyonel)
from sklearn.linear_model import LinearRegression
import numpy as np

# Binance websocket için
from binance import ThreadedWebsocketManager
from binance.client import Client

# --- Ayarlar ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
USE_TWITTER_ANALYSIS = os.getenv("USE_TWITTER_ANALYSIS", "True").lower() == "true"

# --- Logger ayarı ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("onchain_alternative")

# --- Binance API ve Websocket ---
class BinanceAnalyzer:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        self.order_book = None
        self.recent_trades = deque(maxlen=500)
        self.large_trades = []
        self.volume_24h = None
        self.ws_manager = None

    def fetch_order_book(self):
        """Order book derinliğini çek"""
        try:
            self.order_book = self.client.get_order_book(symbol=self.symbol, limit=100)
            return self.order_book
        except Exception as e:
            logger.error(f"Order book çekilemedi: {e}")
            return None

    def fetch_recent_trades(self):
        """Son işlemleri çek"""
        try:
            trades = self.client.get_recent_trades(symbol=self.symbol, limit=500)
            self.recent_trades.extend(trades)
            return list(self.recent_trades)
        except Exception as e:
            logger.error(f"Recent trades çekilemedi: {e}")
            return []

    def fetch_24h_volume(self):
        """24 saatlik hacmi çek"""
        try:
            ticker = self.client.get_ticker(symbol=self.symbol)
            self.volume_24h = float(ticker['quoteVolume'])
            return self.volume_24h
        except Exception as e:
            logger.error(f"24h hacim çekilemedi: {e}")
            return None

    def detect_large_trades(self, threshold=1000):
        """Anormal büyük işlemleri tespit et"""
        large_trades = []
        try:
            for trade in self.recent_trades:
                qty = float(trade['qty'])
                price = float(trade['price'])
                value = qty * price
                if value > threshold:
                    large_trades.append(trade)
            self.large_trades = large_trades
            return large_trades
        except Exception as e:
            logger.error(f"Büyük işlemler tespit edilemedi: {e}")
            return []

    def whale_activity_score(self):
        """Hacim ve fiyat hareketlerinden balina hareketi tahmini (örnek basit skor)"""
        try:
            large_count = len(self.large_trades)
            score = min(large_count / 10, 1.0)  # 0-1 arası normalize skor
            return score
        except Exception as e:
            logger.error(f"Balina skoru hesaplanamadı: {e}")
            return 0

# --- Twitter Sentiment Analizi ---
class TwitterSentimentAnalyzer:
    def __init__(self, query="BTC", max_tweets=100):
        self.query = query
        self.max_tweets = max_tweets
        self.keywords = ["pump", "dump", "crash", "panic", "fud"]
        self.sentiment_score = 0

        # Twitter API ayarı
        self.client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

    def fetch_tweets(self):
        """Twitter'dan coin ile ilgili tweetleri çek"""
        try:
            tweets = self.client.search_recent_tweets(
                query=f"{self.query} {' OR '.join(self.keywords)} lang:en -is:retweet",
                max_results=min(self.max_tweets, 100),
                tweet_fields=["text"]
            )
            return [tweet.text for tweet in tweets.data] if tweets.data else []
        except Exception as e:
            logger.error(f"Tweet çekilemedi: {e}")
            if "429" in str(e):
                # Rate limit yedik, bu döngüde Twitter analizini atla
                return []
            return []

    def analyze_sentiment(self, tweets):
        """Tweetlerde sentiment analizi yap"""
        try:
            total_score = 0
            for tweet in tweets:
                analysis = TextBlob(tweet)
                total_score += analysis.sentiment.polarity
            self.sentiment_score = total_score / len(tweets) if tweets else 0
            return self.sentiment_score
        except Exception as e:
            logger.error(f"Sentiment analizi yapılamadı: {e}")
            return 0

# --- CoinGecko Makro Veriler ---
class CoinGeckoAnalyzer:
    def __init__(self, coin_id="bitcoin"):
        self.coin_id = coin_id

    def fetch_market_data(self):
        """Marketcap, dominance, toplam arz gibi verileri çek"""
        try:
            url = f"{COINGECKO_API_URL}/coins/{self.coin_id}"
            resp = requests.get(url)
            data = resp.json()
            marketcap = data["market_data"]["market_cap"]["usd"]
            dominance = data["market_data"]["market_cap_rank"]
            total_supply = data["market_data"]["total_supply"]
            return {
                "marketcap": marketcap,
                "dominance": dominance,
                "total_supply": total_supply
            }
        except Exception as e:
            logger.error(f"CoinGecko verisi çekilemedi: {e}")
            return {}

# --- Basit Pattern Algoritması (Opsiyonel ML) ---
class SimpleTrendPredictor:
    def __init__(self):
        self.model = LinearRegression()

    def fit(self, prices, volumes):
        """Fiyat ve hacim ile basit trend tahmini"""
        try:
            X = np.array(volumes).reshape(-1, 1)
            y = np.array(prices)
            self.model.fit(X, y)
        except Exception as e:
            logger.error(f"ML modeli eğitilemedi: {e}")

    def predict(self, next_volume):
        """Sonraki hacim için fiyat tahmini"""
        try:
            pred = self.model.predict(np.array([[next_volume]]))
            return float(pred[0])
        except Exception as e:
            logger.error(f"ML tahmini yapılamadı: {e}")
            return None

# --- Ana analiz fonksiyonu ---
def run_onchain_alternative(symbol="BTCUSDT", coin_id="bitcoin"):
    """Gelişmiş analiz ve sinyal üretimi"""
    results = {}
    
    try:
        # === BİNANCE ANALİZLERİ ===
        binance = BinanceAnalyzer(symbol)
        binance.fetch_order_book()
        binance.fetch_recent_trades()
        binance.fetch_24h_volume()
        binance.detect_large_trades()
        
        whale_score = binance.whale_activity_score()
        results["whale_score"] = whale_score
        volume_24h = binance.volume_24h if binance.volume_24h else 0
        results["volume_24h"] = volume_24h

        # === TWITTER SENTIMENT (OPSIYONEL) ===
        if USE_TWITTER_ANALYSIS:
            try:
                twitter = TwitterSentimentAnalyzer(query=symbol.replace("USDT", ""))
                tweets = twitter.fetch_tweets()
                sentiment = twitter.analyze_sentiment(tweets)
                results["twitter_sentiment"] = sentiment
            except Exception as e:
                logger.warning(f"Twitter analizi başarısız: {e}")
                results["twitter_sentiment"] = 0  # Neutral fallback
        else:
            results["twitter_sentiment"] = 0

        # === COINGECKO MAKRO VERİLER ===
        try:
            cg = CoinGeckoAnalyzer(coin_id)
            macro = cg.fetch_market_data()
            results.update(macro)
            marketcap = results.get("marketcap", 0)
        except Exception as e:
            logger.warning(f"CoinGecko analizi başarısız: {e}")
            marketcap = 0
            results["marketcap"] = 0

        # === FİYAT TREND ANALİZİ ===
        recent_prices = []
        if len(binance.recent_trades) > 10:
            recent_prices = [float(trade['price']) for trade in list(binance.recent_trades)[-10:]]
            price_trend = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
        else:
            price_trend = 0
        results["price_trend"] = price_trend

        # === VOLATİLİTE ===
        if len(recent_prices) > 1:
            volatility = np.std(recent_prices) / np.mean(recent_prices)
        else:
            volatility = 0
        results["volatility"] = volatility

        # === LİKİDİTE SKORU ===
        order_book = binance.order_book if binance.order_book else {"bids": [], "asks": []}
        bid_depth = sum([float(bid[1]) for bid in order_book.get("bids", [])[:5]])  # İlk 5 seviye
        ask_depth = sum([float(ask[1]) for ask in order_book.get("asks", [])[:5]])
        liquidity_score = min(bid_depth, ask_depth)
        results["liquidity_score"] = liquidity_score

        # === RİSK FİLTRELERİ ===
        risk_flags = []
        
        if volatility > 0.05:  # %5'ten yüksek volatilite
            risk_flags.append("Aşırı volatilite")
        if liquidity_score < 500:  # Düşük likidite
            risk_flags.append("Düşük likidite")
        if volume_24h < 500_000:  # Düşük hacim
            risk_flags.append("Düşük hacim")
        if marketcap > 0 and marketcap < 50_000_000:  # Düşük market cap
            risk_flags.append("Düşük market cap")
            
        results["risk_flags"] = risk_flags

        # === AKILLI PUANLAMA SİSTEMİ ===
        score = 0
        max_score = 0
        score_details = {}
        
        # Whale activity (ağırlık: 2)
        if whale_score is not None:
            max_score += 2
            if whale_score > 0.8:
                score += 2
                score_details["whale"] = "Güçlü (2/2)"
            elif whale_score > 0.5:
                score += 1
                score_details["whale"] = "Orta (1/2)"
            else:
                score_details["whale"] = "Zayıf (0/2)"
        
        # Price trend (ağırlık: 2)
        if price_trend is not None:
            max_score += 2
            if abs(price_trend) > 0.15:  # %0.15'ten büyük hareket
                if price_trend > 0:
                    score += 2
                    score_details["trend"] = "Güçlü Pozitif (2/2)"
                else:
                    score += 1  # Negatif trend için 1 puan (SELL fırsatı)
                    score_details["trend"] = "Negatif (1/2)"
            elif abs(price_trend) > 0.05:
                score += 1
                score_details["trend"] = "Zayıf (1/2)"
            else:
                score_details["trend"] = "Yatay (0/2)"
        
        # Volume analizi (ağırlık: 1)
        if volume_24h > 0:
            max_score += 1
            if volume_24h > 2_000_000:
                score += 1
                score_details["volume"] = "Yüksek (1/1)"
            else:
                score_details["volume"] = "Düşük (0/1)"
        
        # Likidite analizi (ağırlık: 1)
        if liquidity_score is not None:
            max_score += 1
            if liquidity_score > 1000:
                score += 1
                score_details["liquidity"] = "İyi (1/1)"
            else:
                score_details["liquidity"] = "Düşük (0/1)"
        
        # Volatilite analizi (ağırlık: 1) - düşük volatilite tercih edilir
        if volatility is not None:
            max_score += 1
            if volatility < 0.02:  # %2'den düşük volatilite
                score += 1
                score_details["volatility"] = "Düşük/İyi (1/1)"
            else:
                score_details["volatility"] = "Yüksek (0/1)"
        
        # Twitter sentiment (opsiyonel, ağırlık: 1)
        twitter_sentiment = results.get("twitter_sentiment", 0)
        if twitter_sentiment != 0:  # Sadece veri varsa dahil et
            max_score += 1
            if twitter_sentiment > 0.2:
                score += 1
                score_details["sentiment"] = "Pozitif (1/1)"
            elif twitter_sentiment < -0.2:
                score_details["sentiment"] = "Negatif (0/1)"
            else:
                score_details["sentiment"] = "Nötr (0/1)"

        # === KARAR ALGORİTMASI ===
        min_required_score = max(4, max_score * 0.6)  # En az %60 puan gerekli
        
        if len(risk_flags) > 0:
            trade_signal = "WAIT"
            decision_reason = f"Risk var: {', '.join(risk_flags)}"
        elif score >= min_required_score:
            if price_trend > 0.1:
                trade_signal = "BUY"
                decision_reason = f"Pozitif trend, güçlü sinyal (Score: {score}/{max_score})"
            elif price_trend < -0.1:
                trade_signal = "SELL"
                decision_reason = f"Negatif trend, sat sinyali (Score: {score}/{max_score})"
            else:
                trade_signal = "WAIT"
                decision_reason = f"Yeterli puan ama trend belirsiz (Score: {score}/{max_score})"
        else:
            trade_signal = "WAIT"
            decision_reason = f"Yetersiz puan (Score: {score}/{max_score}, min: {min_required_score})"

        # === SONUÇ ===
        results.update({
            "trade_signal": trade_signal,
            "decision_reason": decision_reason,
            "score": score,
            "max_score": max_score,
            "score_details": score_details,
            "min_required_score": min_required_score
        })
        
        return results
        
    except Exception as e:
        logger.error(f"Analiz hatası ({symbol}): {e}")
        return {
            "trade_signal": "WAIT",
            "decision_reason": f"Analiz hatası: {e}",
            "whale_score": 0,
            "twitter_sentiment": 0,
            "price_trend": 0
        }

# --- Trade sinyali üretici örnek fonksiyon ---
def get_trade_signal(symbol="BTCUSDT", coin_id="bitcoin"):
    """
    Kar odaklı trade sinyali üretir - tüm piyasa koşullarında çalışır
    """
    onchain_data = run_onchain_alternative(symbol=symbol, coin_id=coin_id)
    
    # run_onchain_alternative'den gelen trade_signal'i direkt kullan
    trade_signal = onchain_data.get("trade_signal", "WAIT")
    
    return {
        "trade_signal": trade_signal,
        "whale_score": onchain_data.get("whale_score", 0),
        "twitter_sentiment": onchain_data.get("twitter_sentiment", 0),
        "marketcap": onchain_data.get("marketcap", 0),
        "onchain_data": onchain_data
    }

# --- Test için ---
# trade_signal = random.choice(["BUY", "SELL", "WAIT"])

# --- Örnek kullanım ---
if __name__ == "__main__":
    result = get_trade_signal(symbol="BTCUSDT", coin_id="bitcoin")
    print("Trade Sinyali:", result["trade_signal"])
    print("Detaylı Onchain Analiz:", result["onchain_data"])
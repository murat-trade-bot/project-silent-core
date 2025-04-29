import requests
import time
import json
import random
from datetime import datetime, timedelta
from core.logger import BotLogger
from anti_binance_tespit import anti_detection
from config import settings  # eklendi

logger = BotLogger()

# --- Statik, önerilen coin listesi ve kategorileri ---
RECOMMENDED_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "DOGEUSDT", "SHIBUSDT", "TRXUSDT", "AVAXUSDT",
    "MATICUSDT", "RUNEUSDT", "GALAUSDT", "TIAUSDT",
    "1000SATSUSDT", "PEPEUSDT", "FLOKIUSDT",
    "MEMEUSDT", "WIFUSDT"
]

RECOMMENDED_CATEGORIES = {
    "BTCUSDT": "Major",           "ETHUSDT": "Major",
    "BNBUSDT": "Major",           "SOLUSDT": "Major",
    "DOGEUSDT": "Midcap Meme",    "SHIBUSDT": "Midcap Meme",
    "TRXUSDT": "Midcap",          "AVAXUSDT": "Midcap",
    "MATICUSDT": "Midcap",        "RUNEUSDT": "Midcap",
    "GALAUSDT": "Alt/Microcap",   "TIAUSDT": "Alt/Microcap",
    "1000SATSUSDT": "Microcap Meme", "PEPEUSDT": "Microcap Meme",
    "FLOKIUSDT": "Microcap Meme",   "MEMEUSDT": "Microcap Meme",
    "WIFUSDT": "Microcap Meme"
}

class AssetSelector:
    def __init__(self):
        self.cache = {}
        self.cache_expiry = 3600  # 1 saat
        self.min_volume_usdt = 10_000_000   # 10 milyon USDT
        self.min_market_cap_usdt = 100_000_000  # 100 milyon USDT
        self.max_assets = 5  # Maksimum seçilecek varlık sayısı
        
    def get_cached_assets(self):
        """Önbellekten varlık listesini alır"""
        if "assets" in self.cache:
            timestamp, value = self.cache["assets"]
            if datetime.now().timestamp() - timestamp < self.cache_expiry:
                return value
        return None
        
    def cache_assets(self, assets):
        """Varlık listesini önbelleğe alır"""
        self.cache["assets"] = (datetime.now().timestamp(), assets)
        
    def get_all_symbols(self):
        """Tüm sembolleri alır"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/exchangeInfo"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            if response.status_code == 200:
                data = response.json()
                symbols = []
                for info in data.get("symbols", []):
                    if info.get("status") == "TRADING" and info.get("quoteAsset") == "USDT":
                        symbols.append(info.get("symbol"))
                return symbols
            return []
        except Exception as e:
            logger.log(f"[ASSET] Sembol listesi hatası: {e}", level="ERROR")
            return []
            
    def get_24h_stats(self, symbols):
        """24 saatlik istatistikleri alır"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/ticker/24hr"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            stats = {}
            for symbol in symbols:
                params = {"symbol": symbol}
                resp = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
                if resp.status_code == 200:
                    d = resp.json()
                    stats[symbol] = {
                        "volume": float(d.get("volume", 0)),
                        "quoteVolume": float(d.get("quoteVolume", 0)),
                        "priceChangePercent": float(d.get("priceChangePercent", 0)),
                        "count": int(d.get("count", 0))
                    }
                time.sleep(0.1)
            return stats
        except Exception as e:
            logger.log(f"[ASSET] 24h istatistikleri hatası: {e}", level="ERROR")
            return {}
            
    def get_market_caps(self, symbols):
        """Piyasa değerlerini alır"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/ticker/price"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            caps = {}
            for symbol in symbols:
                params = {"symbol": symbol}
                resp = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
                if resp.status_code == 200:
                    price = float(resp.json().get("price", 0))
                    supply = random.uniform(1_000_000, 100_000_000)
                    caps[symbol] = price * supply
                time.sleep(0.1)
            return caps
        except Exception as e:
            logger.log(f"[ASSET] Piyasa değeri hatası: {e}", level="ERROR")
            return {}
            
    def calculate_volatility(self, symbol):
        """Volatilite hesaplar"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": "1h", "limit": 24}
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            resp = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 24:
                    closes = [float(c[4]) for c in data]
                    return (max(closes) - min(closes)) / min(closes) * 100
            return 0
        except Exception as e:
            logger.log(f"[ASSET] Volatilite hesaplama hatası: {e}", level="ERROR")
            return 0
            
    def score_assets(self, symbols, stats, market_caps):
        """Varlıkları puanlar"""
        scores = {}
        for s in symbols:
            if s not in stats or s not in market_caps:
                continue
            stat = stats[s]; cap = market_caps[s]
            if stat["quoteVolume"] < self.min_volume_usdt or cap < self.min_market_cap_usdt:
                continue
            vol = self.calculate_volatility(s)
            score = min(30, stat["quoteVolume"]/self.min_volume_usdt*10)
            score += min(20, cap/self.min_market_cap_usdt*10)
            score += min(10, stat["count"]/1000)
            score += min(20, vol*2)
            score += min(20, abs(stat["priceChangePercent"]))
            scores[s] = score
        return scores
        
    def select_coins(self):
        """En iyi varlıkları seçer"""
        # Eğer dinamik seçim kapalıysa, statik önerilen listeyi kullan
        if not settings.USE_DYNAMIC_SYMBOL_SELECTION:
            return RECOMMENDED_COINS

        # Önbellekten kontrol et
        cached = self.get_cached_assets()
        if cached is not None:
            return cached

        # Dinamik seçim akışı
        all_syms = self.get_all_symbols()
        if not all_syms:
            return ["BTCUSDT"]
        stats = self.get_24h_stats(all_syms)
        if not stats:
            return ["BTCUSDT"]
        caps = self.get_market_caps(all_syms)
        if not caps:
            return ["BTCUSDT"]
        scored = self.score_assets(all_syms, stats, caps)
        # En yüksek puanlıları seç
        top = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:self.max_assets]
        sel = [sym for sym, _ in top]
        if "BTCUSDT" not in sel:
            sel.append("BTCUSDT")
        self.cache_assets(sel)
        return sel

# Global instance
asset_selector = AssetSelector()

def select_coins():
    """Dışa açık fonksiyon"""
    return asset_selector.select_coins()

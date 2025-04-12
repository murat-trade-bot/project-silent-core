import requests
import time
import json
import random
from datetime import datetime, timedelta
from core.logger import BotLogger
from anti_binance_tespit import anti_detection

logger = BotLogger()

class AssetSelector:
    def __init__(self):
        self.cache = {}
        self.cache_expiry = 3600  # 1 saat
        self.min_volume_usdt = 10000000  # 10 milyon USDT
        self.min_market_cap_usdt = 100000000  # 100 milyon USDT
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
                for symbol_info in data.get("symbols", []):
                    if symbol_info.get("status") == "TRADING" and symbol_info.get("quoteAsset") == "USDT":
                        symbols.append(symbol_info.get("symbol"))
                return symbols
            return []
        except Exception as e:
            logger.log(f"[ASSET] Sembol listesi hatası: {e}")
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
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    stats[symbol] = {
                        "volume": float(data.get("volume", 0)),
                        "quoteVolume": float(data.get("quoteVolume", 0)),
                        "priceChangePercent": float(data.get("priceChangePercent", 0)),
                        "count": int(data.get("count", 0))
                    }
                time.sleep(0.1)  # Rate limit için bekleme
            return stats
        except Exception as e:
            logger.log(f"[ASSET] 24h istatistikleri hatası: {e}")
            return {}
            
    def get_market_caps(self, symbols):
        """Piyasa değerlerini alır"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/ticker/price"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            market_caps = {}
            for symbol in symbols:
                params = {"symbol": symbol}
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    price = float(data.get("price", 0))
                    
                    # Dolaşımdaki arz bilgisi (gerçek uygulamada API'den alınmalı)
                    # Şimdilik simüle ediyoruz
                    circulating_supply = random.uniform(1000000, 100000000)
                    
                    market_caps[symbol] = price * circulating_supply
                time.sleep(0.1)  # Rate limit için bekleme
            return market_caps
        except Exception as e:
            logger.log(f"[ASSET] Piyasa değeri hatası: {e}")
            return {}
            
    def calculate_volatility(self, symbol):
        """Volatilite hesaplar"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": "1h",
                "limit": 24
            }
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            
            response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 24:
                    closes = [float(candle[4]) for candle in data]
                    high = max(closes)
                    low = min(closes)
                    volatility = (high - low) / low * 100
                    return volatility
            return 0
        except Exception as e:
            logger.log(f"[ASSET] Volatilite hesaplama hatası: {e}")
            return 0
            
    def score_assets(self, symbols, stats, market_caps):
        """Varlıkları puanlar"""
        scores = {}
        for symbol in symbols:
            if symbol not in stats or symbol not in market_caps:
                continue
                
            stat = stats[symbol]
            market_cap = market_caps[symbol]
            
            # Temel kriterleri kontrol et
            if stat["quoteVolume"] < self.min_volume_usdt:
                continue
            if market_cap < self.min_market_cap_usdt:
                continue
                
            # Volatilite hesapla
            volatility = self.calculate_volatility(symbol)
            
            # Puanlama
            score = 0
            
            # Hacim puanı (0-30)
            volume_score = min(30, stat["quoteVolume"] / self.min_volume_usdt * 10)
            score += volume_score
            
            # Piyasa değeri puanı (0-20)
            market_cap_score = min(20, market_cap / self.min_market_cap_usdt * 10)
            score += market_cap_score
            
            # İşlem sayısı puanı (0-10)
            count_score = min(10, stat["count"] / 1000)
            score += count_score
            
            # Volatilite puanı (0-20)
            volatility_score = min(20, volatility * 2)
            score += volatility_score
            
            # Fiyat değişimi puanı (0-20)
            price_change = abs(stat["priceChangePercent"])
            price_change_score = min(20, price_change)
            score += price_change_score
            
            scores[symbol] = score
            
        return scores
        
    def select_coins(self):
        """En iyi varlıkları seçer"""
        # Önbellekten kontrol et
        cached_assets = self.get_cached_assets()
        if cached_assets is not None:
            return cached_assets
            
        # Tüm sembolleri al
        all_symbols = self.get_all_symbols()
        if not all_symbols:
            return ["BTCUSDT"]
            
        # 24 saatlik istatistikleri al
        stats = self.get_24h_stats(all_symbols)
        if not stats:
            return ["BTCUSDT"]
            
        # Piyasa değerlerini al
        market_caps = self.get_market_caps(all_symbols)
        if not market_caps:
            return ["BTCUSDT"]
            
        # Varlıkları puanla
        scores = self.score_assets(all_symbols, stats, market_caps)
        
        # En yüksek puanlı varlıkları seç
        sorted_assets = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected_assets = [asset for asset, _ in sorted_assets[:self.max_assets]]
        
        # BTCUSDT her zaman listede olsun
        if "BTCUSDT" not in selected_assets:
            selected_assets.append("BTCUSDT")
            
        # Önbelleğe al
        self.cache_assets(selected_assets)
        
        return selected_assets

# Global instance
asset_selector = AssetSelector()

def select_coins():
    """Dışa açık fonksiyon"""
    return asset_selector.select_coins() 
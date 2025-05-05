import requests
import time
import random
import json
from datetime import datetime, timedelta
from core.logger import BotLogger
from anti_binance_tespit import anti_detection
from config import settings
from modules.technical_analysis import fetch_ohlcv_from_binance, calculate_rsi
from modules.domino_effect import detect_domino_effect

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
        # Cache
        self.cache = {}
        self.cache_expiry = getattr(settings, 'ASSET_CACHE_EXPIRY', 3600)  # saniye
        # Settings
        self.min_volume_usdt     = getattr(settings, 'MIN_VOLUME_USDT', 10_000_000)
        self.min_market_cap_usdt = getattr(settings, 'MIN_MARKET_CAP_USDT', 100_000_000)
        self.max_assets          = getattr(settings, 'MAX_ASSETS', 5)

    def get_cached_assets(self):
        """Önbellekten varlık listesini alır"""
        entry = self.cache.get('assets')
        if not entry:
            return None
        ts, assets = entry
        if datetime.now().timestamp() - ts < self.cache_expiry:
            return assets
        return None

    def cache_assets(self, assets):
        """Varlık listesini önbelleğe alır"""
        self.cache['assets'] = (datetime.now().timestamp(), assets)

    def get_all_symbols(self):
        """Tüm USDT çiftlerini Binance API'den alır"""
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/exchangeInfo"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            data = resp.json() if resp.status_code == 200 else {}
            return [s['symbol'] for s in data.get('symbols', [])
                    if s.get('status') == 'TRADING' and s.get('quoteAsset') == 'USDT']
        except Exception as e:
            logger.log(f"[ASSET] get_all_symbols error: {e}", level="ERROR")
            return []

    def get_24h_stats(self, symbols):
        """24 saatlik istatistikleri alır"""
        stats = {}
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/ticker/24hr"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            for sym in symbols:
                resp = requests.get(url, params={'symbol': sym}, headers=headers, proxies=proxies, timeout=5)
                if resp.status_code == 200:
                    d = resp.json()
                    stats[sym] = {
                        'quoteVolume': float(d.get('quoteVolume', 0)),
                        'priceChangePercent': float(d.get('priceChangePercent', 0)),
                        'count': int(d.get('count', 0))
                    }
                time.sleep(0.05)
        except Exception as e:
            logger.log(f"[ASSET] get_24h_stats error: {e}", level="ERROR")
        return stats

    def get_market_caps(self, symbols):
        """Basit piyasa değeri tahmini"""
        caps = {}
        try:
            anti_detection.check_rate_limit()
            url = "https://api.binance.com/api/v3/ticker/price"
            headers = {"User-Agent": anti_detection.get_random_user_agent()}
            proxies = anti_detection.get_next_proxy()
            for sym in symbols:
                resp = requests.get(url, params={'symbol': sym}, headers=headers, proxies=proxies, timeout=5)
                if resp.status_code == 200:
                    price = float(resp.json().get('price', 0))
                    # Not: gerçek circulating supply yok, rastgele tahmin
                    supply = random.uniform(1e6, 1e8)
                    caps[sym] = price * supply
                time.sleep(0.05)
        except Exception as e:
            logger.log(f"[ASSET] get_market_caps error: {e}", level="ERROR")
        return caps

    def score_and_filter(self, symbols, stats, caps):
        """Sembol puanlama ve RSI/domino filtresi"""
        scored = []
        for sym in symbols:
            vol = stats.get(sym, {}).get('quoteVolume', 0)
            cap = caps.get(sym, 0)
            if vol < self.min_volume_usdt or cap < self.min_market_cap_usdt:
                continue
            # Score hesapla
            score = (vol / self.min_volume_usdt) * 10
            score += min(20, cap / self.min_market_cap_usdt * 10)
            score += stats[sym].get('count', 0) / 1000
            # RSI ve domino kontrolü
            try:
                ohlcv = fetch_ohlcv_from_binance(sym, '1h', limit=14)
                rsi = calculate_rsi([c[4] for c in ohlcv])[-1]
                if not (settings.RSI_OVERSOLD < rsi < settings.RSI_OVERBOUGHT):
                    continue
                if detect_domino_effect(sym):
                    continue
            except Exception:
                continue
            scored.append((sym, score))
        # Puanlara göre sırala
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored]

    def select_coins(self):
        """En iyi varlıkları döner"""
        # Statik liste kullan
        if not settings.USE_DYNAMIC_SYMBOL_SELECTION:
            pool = RECOMMENDED_COINS.copy()
            random.shuffle(pool)
            return pool[:self.max_assets]

        # Önbellek kontrolü
        cached = self.get_cached_assets()
        if cached:
            return cached
        # Dinamik akış
        syms = self.get_all_symbols()
        if not syms:
            return RECOMMENDED_COINS[:self.max_assets]
        stats = self.get_24h_stats(syms)
        if not stats:
            return RECOMMENDED_COINS[:self.max_assets]
        caps = self.get_market_caps(syms)
        if not caps:
            return RECOMMENDED_COINS[:self.max_assets]
        candidates = self.score_and_filter(syms, stats, caps)
        # İlk max_assets adedekini al
        selected = candidates[:self.max_assets]
        # Her zaman en az bir BTC olsun
        if "BTCUSDT" not in selected:
            selected[-1] = "BTCUSDT"
        random.shuffle(selected)
        # Önbelleğe kaydet
        self.cache_assets(selected)
        return selected

# Global instance
asset_selector = AssetSelector()

def select_coins():
    """Bot döngüsünden çağrılacak"""
    return asset_selector.select_coins()

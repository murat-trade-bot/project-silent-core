"""
Onchain Tracking Module
Büyük transferleri, balina hareketlerini, aktif adresleri ve borsa giriş/çıkışlarını izler.
Stealth mod, hata toleransı, retry/backoff ve dönemsel risk yönetimi için uygundur.
"""

import requests
import random
import time
from core.logger import BotLogger
from config import settings

logger = BotLogger()

class OnchainTracking:
    def __init__(self):
        self.api_key = getattr(settings, "GLASSNODE_API_KEY", None)
        self.base_url = "https://api.glassnode.com/v1/metrics"
        self.headers = {"X-Api-Key": self.api_key, "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourproject)"} if self.api_key else {}

    def _request_with_retry(self, url, params, retries=3):
        for attempt in range(retries):
            try:
                time.sleep(random.uniform(0.3, 1.2))
                r = requests.get(url, params=params, headers=self.headers, timeout=7)
                if r.status_code == 429:
                    logger.warning("OnchainTracking: API rate limit aşıldı (429). Kısa süre bekleniyor.")
                    time.sleep(2)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as e:
                logger.error(f"OnchainTracking: API error (attempt {attempt+1}): {e}")
                time.sleep(1.5 * (attempt + 1))
        logger.warning("OnchainTracking: API başarısız, dummy veri dönülüyor.")
        return None

    def fetch_large_transfers(self, asset: str = "BTC") -> int:
        """
        Büyük transfer sayısını çeker (ör: Glassnode API).
        """
        if not self.api_key:
            logger.warning("OnchainTracking: API anahtarı yok, dummy veri kullanılacak.")
            return random.randint(0, 10)
        url = f"{self.base_url}/transactions/transfers_volume_sum"
        params = {"a": asset, "api_key": self.api_key}
        data = self._request_with_retry(url, params)
        try:
            value = int(data[-1]["v"]) if data else random.randint(0, 10)
        except Exception as e:
            logger.error(f"OnchainTracking: fetch_large_transfers veri hatası: {e}")
            value = random.randint(0, 10)
        logger.info(f"OnchainTracking: {asset} large transfers: {value}")
        return value

    def fetch_active_addresses(self, asset: str = "BTC") -> int:
        """
        Aktif adres sayısını çeker.
        """
        if not self.api_key:
            logger.warning("OnchainTracking: API anahtarı yok, dummy veri kullanılacak.")
            return random.randint(100_000, 1_000_000)
        url = f"{self.base_url}/addresses/active_count"
        params = {"a": asset, "api_key": self.api_key}
        data = self._request_with_retry(url, params)
        try:
            value = int(data[-1]["v"]) if data else random.randint(100_000, 1_000_000)
        except Exception as e:
            logger.error(f"OnchainTracking: fetch_active_addresses veri hatası: {e}")
            value = random.randint(100_000, 1_000_000)
        logger.info(f"OnchainTracking: {asset} active addresses: {value}")
        return value

    def fetch_exchange_flows(self, asset: str = "BTC") -> float:
        """
        Borsalara giriş/çıkış miktarını çeker.
        """
        if not self.api_key:
            logger.warning("OnchainTracking: API anahtarı yok, dummy veri kullanılacak.")
            return random.uniform(-5000, 5000)
        url = f"{self.base_url}/distribution/exchange_net_position_change"
        params = {"a": asset, "api_key": self.api_key}
        data = self._request_with_retry(url, params)
        try:
            value = float(data[-1]["v"]) if data else random.uniform(-5000, 5000)
        except Exception as e:
            logger.error(f"OnchainTracking: fetch_exchange_flows veri hatası: {e}")
            value = random.uniform(-5000, 5000)
        logger.info(f"OnchainTracking: {asset} exchange net flow: {value}")
        return value

    def whale_alert_score(self, asset: str = "BTC", period_multiplier: float = 1.0) -> float:
        """
        Balina hareketlerine ve diğer zincir üstü metriklere göre dönemsel risk skoru üretir.
        """
        transfers = self.fetch_large_transfers(asset)
        active_addresses = self.fetch_active_addresses(asset)
        exchange_flow = self.fetch_exchange_flows(asset)
        # Normalize ve ağırlıklandır
        transfer_score = min(1.0, transfers / 10)
        address_score = 1.0 - min(1.0, (active_addresses - 100_000) / 900_000)  # az aktif adres = yüksek risk
        flow_score = min(1.0, abs(exchange_flow) / 5000)  # büyük giriş/çıkış = yüksek risk
        # Kompozit skor, dönemsel ağırlık ile
        score = (transfer_score * 0.5 + address_score * 0.3 + flow_score * 0.2) * period_multiplier
        score = max(0, min(1, score))
        logger.info(f"OnchainTracking: Composite whale alert score: {score:.2f}")
        return score

    def dry_run(self):
        """
        Test amaçlı örnek skor üretir.
        """
        logger.info("OnchainTracking: Dry-run başlatıldı.")
        return {
            "large_transfers": self.fetch_large_transfers(),
            "active_addresses": self.fetch_active_addresses(),
            "exchange_flows": self.fetch_exchange_flows(),
            "whale_alert_score": self.whale_alert_score()
        }

def track_onchain_activity(asset: str = "BTC") -> dict:
    """
    OnchainTracking sınıfını kullanarak zincir üstü temel metrikleri döndürür.
    """
    tracker = OnchainTracking()
    return {
        "large_transfers": tracker.fetch_large_transfers(asset),
        "active_addresses": tracker.fetch_active_addresses(asset),
        "exchange_flows": tracker.fetch_exchange_flows(asset),
        "whale_alert_score": tracker.whale_alert_score(asset)
    }

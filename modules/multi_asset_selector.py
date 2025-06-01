"""
Multi Asset Selector Module
Binance Spot'tan uygun coinleri çeker, insanvari ve rastgele seçimle işlem yapılacakları belirler.
Stealth mod, risk ve çeşitlilik için uygundur.
"""

import requests
import random
import time
from typing import List
from core.logger import BotLogger

logger = BotLogger()

class MultiAssetSelector:
    def __init__(self):
        self.base_asset = "USDT"
        self.min_volume = 1_000_000  # Minimum 24h hacim (örnek)
        self.blacklist = ["BUSD", "USDC", "TUSD", "FDUSD"]

    def fetch_spot_symbols(self) -> List[str]:
        """
        Binance Spot'tan USDT paritelerini ve hacimlerini çeker.
        """
        url = "https://api.binance.com/api/v3/ticker/24hr"
        try:
            # Stealth: Rastgele gecikme
            time.sleep(random.uniform(0.5, 2.0))
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            symbols = []
            for item in data:
                symbol = item["symbol"]
                if not symbol.endswith(self.base_asset):
                    continue
                if any(bad in symbol for bad in self.blacklist):
                    continue
                try:
                    volume = float(item["quoteVolume"])
                except Exception:
                    continue
                if volume < self.min_volume:
                    continue
                symbols.append(symbol)
            logger.info(f"MultiAssetSelector: {len(symbols)} uygun coin bulundu.")
            return symbols
        except Exception as e:
            logger.error(f"MultiAssetSelector fetch error: {e}")
            return []

    def select_assets(self, count: int = 3) -> List[str]:
        """
        Rastgele veya ağırlıklı seçimle işlem yapılacak coinleri belirler.
        """
        symbols = self.fetch_spot_symbols()
        if not symbols:
            logger.warning("Hiç uygun coin bulunamadı, BTCUSDT seçiliyor.")
            return ["BTCUSDT"]
        # Stealth: Rastgele seçim, insanvari davranış
        selected = random.sample(symbols, min(count, len(symbols)))
        logger.info(f"Seçilen coinler: {selected}")
        return selected

# DİKKAT: select_coins fonksiyonu SINIF DIŞINDA OLMALI!
def select_coins(market_data: dict = None, top_n: int = 3) -> list:
    """
    Piyasadan en yüksek skorlu/top hacimli ilk N coini seçer.
    market_data: {"BTC": skor, "ETH": skor, ...}
    top_n: Kaç coin seçilecek
    """
    if not market_data:
        # Dummy veri döndür
        return ["BTC", "ETH", "BNB"][:top_n]
    sorted_coins = sorted(market_data.items(), key=lambda x: x[1], reverse=True)
    return [coin for coin, score in sorted_coins[:top_n]]

def main_loop():
    selector = MultiAssetSelector()
    while True:
        try:
            # Her döngüde farklı sayıda varlık seçimi yap
            count = random.randint(1, 5)
            selector.select_assets(count)
            # Stealth: Döngüler arası rastgele gecikme
            time.sleep(random.uniform(10, 30))
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)  # Hata durumunda bekle ve tekrar dene

if __name__ == "__main__":
    main_loop()

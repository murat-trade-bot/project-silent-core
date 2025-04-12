import requests
from config import settings

class OrderBookAnalyzer:
    def __init__(self):
        self.symbol = settings.SYMBOL
        self.limit = 100
        self.api_url = "https://api.binance.com/api/v3/depth"

    def fetch_orderbook(self):
        try:
            params = {"symbol": self.symbol, "limit": self.limit}
            r = requests.get(self.api_url, params=params, timeout=5)
            data = r.json()
            if "bids" in data and "asks" in data:
                return data["bids"], data["asks"]
        except:
            pass
        return [], []

    def analyze_liquidity_zones(self):
        bids, asks = self.fetch_orderbook()
        if not bids or not asks:
            return {"liquidity_pressure": "neutral"}
        total_bids = sum(float(b[1]) for b in bids)
        total_asks = sum(float(a[1]) for a in asks)
        imbalance = total_bids - total_asks
        pressure = "buy_pressure" if imbalance > 0 else "sell_pressure" if imbalance < 0 else "neutral"
        volume_ratio = total_bids / total_asks if total_asks else 1
        return {"liquidity_pressure": pressure, "volume_ratio": round(volume_ratio, 2)} 
"""
Order Executor Module
Strateji ve portföy yönetiminden gelen sinyalleri gerçek emir(ler)e dönüştürür.
Stealth mod, hata toleransı, insanvari zamanlama ve 6 dönemlik kazanç planı ile tam uyumludur.
"""

import random
import time
from core.logger import BotLogger
from config import settings
from modules.order_executor import OrderExecutor

logger = BotLogger()

class OrderExecutor:
    def __init__(self, api_client):
        self.api_client = api_client  # Binance veya başka bir borsa API client'ı
        self.max_retry = 3

    def _stealth_delay(self):
        time.sleep(random.uniform(0.4, 2.2))

    def execute_order(self, symbol, side, quantity, order_type="MARKET", price=None):
        """
        Gerçek emir gönderir. Stealth mod, retry ve hata toleransı içerir.
        """
        for attempt in range(self.max_retry):
            try:
                self._stealth_delay()
                logger.info(f"OrderExecutor: {side} {quantity} {symbol} ({order_type}) gönderiliyor (deneme {attempt+1})")
                if order_type == "MARKET":
                    result = self.api_client.create_market_order(symbol, side, quantity)
                elif order_type == "LIMIT" and price:
                    result = self.api_client.create_limit_order(symbol, side, quantity, price)
                else:
                    raise ValueError("Geçersiz order_type veya eksik fiyat.")
                logger.info(f"OrderExecutor: Emir başarılı! Sonuç: {result}")
                return result
            except Exception as e:
                logger.error(f"OrderExecutor: Emir hatası (deneme {attempt+1}): {e}")
                time.sleep(1.5 * (attempt + 1))
        logger.warning(f"OrderExecutor: Emir başarısız oldu, {side} {quantity} {symbol}")
        return None

    def batch_execute(self, orders):
        """
        Birden fazla emri sırayla ve stealth modda uygular.
        orders: [{'symbol': 'BTCUSDT', 'side': 'BUY', 'quantity': 0.01, ...}, ...]
        """
        results = []
        for order in orders:
            result = self.execute_order(
                order.get("symbol"),
                order.get("side"),
                order.get("quantity"),
                order.get("order_type", "MARKET"),
                order.get("price")
            )
            results.append(result)
        return results

    def place_order(self, symbol, side, quantity, order_type="MARKET", price=None):
        """
        Dışarıdan erişim için bir sarıcıdır. OrderExecutor'ün execute_order metodunu çağırır.
        """
        return self.execute_order(symbol, side, quantity, order_type, price)
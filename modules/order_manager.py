# order_manager.py
"""
Scalping odaklı, TP/SL'li emir yönetimi modülü
"""
import logging
from typing import Optional, Dict, Any



import csv
import os as _os

class OrderManager:
    def __init__(self, client, symbol: str, qty: float, tp_pct: float = 0.4, sl_pct: float = 0.2, log_file: str = 'order_manager.log', csv_log: str = 'trade_history.csv'):
        self.client = client
        self.symbol = symbol
        self.qty = qty
        self.tp_pct = tp_pct  # % olarak kar hedefi
        self.sl_pct = sl_pct  # % olarak zarar limiti
        self.csv_log = csv_log
        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    def _get_symbol_filters(self):
        """Binance exchangeInfo'dan min qty, tick size, step vs. çeker."""
        try:
            info = self.client.get_symbol_info(self.symbol)
            filters = {f['filterType']: f for f in info['filters']}
            return filters
        except Exception as e:
            logging.error(f"Symbol info error: {e}")
            return {}


    def _round_to_step(self, value, step):
        """Fiyatı/qty'yi adımına yuvarlar."""
        import math
        return float(format(math.floor(float(value) / float(step)) * float(step), f'.{str(step)[::-1].find(".")}f'))

    def place_scalping_order(self, side: str, entry_price: float) -> Optional[Dict[str, Any]]:
        """
        Binance Spot için: Market giriş + OCO ile TP/SL. Emir ve sonuçlarını loglar.
        Fiyat/qty validasyonu, fill_price ile TP/SL, OCO orderId logu, CSV logu.
        """
        filters = self._get_symbol_filters()
        lot_step = filters.get('LOT_SIZE', {}).get('stepSize', '0.00001')
        min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0.0))
        price_step = filters.get('PRICE_FILTER', {}).get('tickSize', '0.01')

        qty = max(self.qty, min_qty)
        qty = self._round_to_step(qty, lot_step)

        try:
            order = self.client.create_order(
                symbol=self.symbol,
                side=side.upper(),
                type='MARKET',
                quantity=qty
            )
            fill_price = float(order.get('fills', [{}])[0].get('price', entry_price))
            logging.info(f"Market order sent: {order}")
        except Exception as e:
            logging.error(f"Order send error: {e}")
            return None

        # TP/SL fiyatlarını fill_price ile ve adımına uygun hesapla
        if side.lower() == 'buy':
            tp_price = fill_price * (1 + self.tp_pct / 100)
            sl_price = fill_price * (1 - self.sl_pct / 100)
            oco_side = 'SELL'
        else:
            tp_price = fill_price * (1 - self.tp_pct / 100)
            sl_price = fill_price * (1 + self.sl_pct / 100)
            oco_side = 'BUY'

        tp_price = self._round_to_step(tp_price, price_step)
        # stopPrice ve stopLimitPrice arasında küçük fark (örn. 0.1%)
        stop_price = self._round_to_step(sl_price, price_step)
        stop_limit_price = self._round_to_step(sl_price * 0.999, price_step) if side.lower() == 'buy' else self._round_to_step(sl_price * 1.001, price_step)

        # OCO ile TP/SL emirlerini gönder (Binance Spot)
        try:
            oco_order = self.client.create_oco_order(
                symbol=self.symbol,
                side=oco_side,
                quantity=qty,
                price=str(tp_price),
                stopPrice=str(stop_price),
                stopLimitPrice=str(stop_limit_price),
                stopLimitTimeInForce='GTC'
            )
            logging.info(f"OCO order sent: {oco_order}")
            # OCO orderId ve alt orderId'leri logla
            oco_ids = {
                'orderListId': oco_order.get('orderListId'),
                'orders': [o.get('orderId') for o in oco_order.get('orders', [])]
            }
            logging.info(f"OCO IDs: {oco_ids}")
            self._log_trade_csv(order, oco_order, fill_price)
            return {
                'entry': order,
                'oco': oco_order,
                'oco_ids': oco_ids
            }
        except Exception as e:
            logging.error(f"OCO order error: {e}")
            self._log_trade_csv(order, None, fill_price)
            return {'entry': order, 'oco': None}

    def _log_trade_csv(self, entry_order, oco_order, fill_price):
        """Temel trade geçmişi CSV logu."""
        file_exists = _os.path.isfile(self.csv_log)
        with open(self.csv_log, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(['entry_orderId', 'oco_orderListId', 'fill_price', 'symbol', 'qty', 'tp', 'sl'])
            writer.writerow([
                entry_order.get('orderId'),
                oco_order.get('orderListId') if oco_order else None,
                fill_price,
                self.symbol,
                self.qty,
                (oco_order.get('orders', [{}])[0].get('price') if oco_order else None),
                (oco_order.get('orders', [{}])[-1].get('stopPrice') if oco_order else None)
            ])

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        try:
            status = self.client.get_order(symbol=self.symbol, orderId=order_id)
            logging.info(f"Order status: {status}")
            return status
        except Exception as e:
            logging.error(f"Order status error: {e}")
            return None

    def cancel_all_orders(self):
        try:
            result = self.client.cancel_open_orders(symbol=self.symbol)
            logging.info(f"All open orders cancelled: {result}")
            return result
        except Exception as e:
            logging.error(f"Cancel orders error: {e}")
            return None

# Test fonksiyonu (mock client ile)

def test_order_manager():
    class MockClient:
        def create_order(self, **kwargs):
            return {'mock_order': kwargs}
        def create_oco_order(self, **kwargs):
            return {'mock_oco_order': kwargs}
        def cancel_open_orders(self, symbol):
            return {'cancelled': symbol}
        def get_order(self, symbol, orderId):
            return {'orderId': orderId, 'status': 'FILLED'}

    om = OrderManager(MockClient(), 'BTCUSDT', 0.01)
    result = om.place_scalping_order('buy', 10000)
    print('Order result:', result)
    cancel_result = om.cancel_all_orders()
    print('Cancel result:', cancel_result)
    status = om.get_order_status('12345')
    print('Order status:', status)

if __name__ == "__main__":
    test_order_manager()

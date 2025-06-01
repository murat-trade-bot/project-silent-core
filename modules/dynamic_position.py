"""
Dynamic Position Module
Pozisyon büyüklüğü ve risk seviyesini dönemsel hedeflere ve piyasa koşullarına göre dinamik ayarlar.
Stealth mod ve insanvari davranış için uygundur.
"""

import random
from typing import Optional

from core.logger import BotLogger
from config import settings

logger = BotLogger()


class DynamicPosition:
    def __init__(self, min_risk=0.005, max_risk=0.02):
        self.min_risk = min_risk
        self.max_risk = max_risk

    def calculate_position_size(self, portfolio_value, price, max_position_pct, split_pct=1.0):
        """
        Pozisyon büyüklüğünü dinamik olarak hesaplar.
        """
        return (max_position_pct * portfolio_value * split_pct) / price

    def adjust_stop_take(self, entry_price: float, atr: float, atr_multiplier: float = 2.0):
        """
        ATR'ye göre dinamik stop-loss ve take-profit seviyeleri belirler.
        """
        stop_loss = entry_price - atr * atr_multiplier * random.uniform(0.95, 1.05)
        take_profit = entry_price + atr * atr_multiplier * random.uniform(0.95, 1.10)
        logger.info(f"DynamicPosition: Stop-loss {stop_loss:.2f}, Take-profit {take_profit:.2f}")
        return stop_loss, take_profit

def get_dynamic_position_size(
    atr_value: Optional[float],
    base_position_pct: float
) -> float:
    """
    Returns an adjusted position size percentage based on ATR (Average True Range).

    - If ATR value is None or invalid, returns the base percentage.
    - If ATR is above high threshold, reduces position size.
    - If ATR is below low threshold, increases position size.

    Thresholds are configurable via settings:
      - ATR_HIGH_THRESHOLD (default 100)
      - ATR_LOW_THRESHOLD  (default 30)
      - ATR_REDUCE_FACTOR  (default 0.5)
      - ATR_INCREASE_FACTOR(default 1.5)
    """
    try:
        # Use settings if available, else defaults
        high_thr = getattr(settings, 'ATR_HIGH_THRESHOLD', 100.0)
        low_thr = getattr(settings, 'ATR_LOW_THRESHOLD', 30.0)
        reduce_factor = getattr(settings, 'ATR_REDUCE_FACTOR', 0.5)
        increase_factor = getattr(settings, 'ATR_INCREASE_FACTOR', 1.5)

        if atr_value is None:
            return base_position_pct

        if atr_value > high_thr:
            adjusted = base_position_pct * reduce_factor
            logger.info(
                f"DynamicPosition: ATR={atr_value:.2f} > {high_thr}, "
                f"reducing position to {adjusted:.4f}"
            )
            return adjusted

        if atr_value < low_thr:
            adjusted = base_position_pct * increase_factor
            logger.info(
                f"DynamicPosition: ATR={atr_value:.2f} < {low_thr}, "
                f"increasing position to {adjusted:.4f}"
            )
            return adjusted

        # ATR within normal range
        return base_position_pct

    except Exception as e:
        logger.error(f"[DYNAMIC_POS] Error calculating dynamic position size: {e}")
        return base_position_pct

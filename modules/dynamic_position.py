"""
Module: dynamic_position.py
Adjusts base position size percentage dynamically based on market volatility (ATR indicator).
Includes error handling and customizable thresholds via settings.
"""
from typing import Optional

from core.logger import BotLogger
from config import settings

logger = BotLogger()


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

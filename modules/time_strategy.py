"""
Module: time_strategy.py
Determines the current trading regime based on UTC time, weekday, month, and special dates.
Includes error handling and customizable parameters via settings.
"""

from datetime import datetime
from typing import Literal
from config import settings
from core.logger import BotLogger

logger = BotLogger()

StrategyMode = Literal[
    'auto_close', 'aggressive', 'passive', 'defensive',
    'volatility_focus', 'weekend_mode', 'entry_focus', 'exit_focus', 'neutral'
]

SPECIAL_CLOSURE_DATES = getattr(settings, 'STRATEGY_CLOSURE_DATES', ['12-25'])


def get_current_strategy_mode(now: datetime = None) -> StrategyMode:
    """
    Returns the current strategy mode based on UTC time and configured rules.
    now: test amaçlı dışarıdan datetime verilebilir.
    """
    try:
        now = now or datetime.utcnow()
        month_day = now.strftime('%m-%d')
        weekday = now.weekday()
        hour = now.hour
        day = now.day

        # Auto-close on special dates
        if month_day in SPECIAL_CLOSURE_DATES:
            logger.info(f"[TIME_STRATEGY] Auto-close mode: {month_day} özel gün.")
            return 'auto_close'

        # Market open aggressive window
        open_start, open_end = getattr(settings, 'AGGRESSIVE_HOURS', (8, 10))
        if open_start <= hour < open_end:
            logger.info(f"[TIME_STRATEGY] Aggressive mode: Saat {hour} ({open_start}-{open_end}) arası.")
            return 'aggressive'

        # Nighttime passive window
        passive_start, passive_end = getattr(settings, 'PASSIVE_HOURS', (22, 2))
        if passive_start <= hour or hour < passive_end:
            logger.info(f"[TIME_STRATEGY] Passive mode: Saat {hour} ({passive_start}-{passive_end}) arası.")
            return 'passive'

        # Weekday rules
        if weekday == 0:
            logger.info("[TIME_STRATEGY] Defensive mode: Pazartesi.")
            return 'defensive'
        if weekday == 4:
            logger.info("[TIME_STRATEGY] Volatility focus: Cuma.")
            return 'volatility_focus'
        if weekday in (5, 6):
            logger.info("[TIME_STRATEGY] Weekend mode: Cumartesi/Pazar.")
            return 'weekend_mode'

        # Day of month rules
        entry_limit = getattr(settings, 'ENTRY_FOCUS_DAY_END', 5)
        exit_start = getattr(settings, 'EXIT_FOCUS_DAY_START', 25)
        if day <= entry_limit:
            logger.info(f"[TIME_STRATEGY] Entry focus: Ayın ilk {entry_limit} günü.")
            return 'entry_focus'
        if day >= exit_start:
            logger.info(f"[TIME_STRATEGY] Exit focus: Ayın {exit_start}. gününden sonrası.")
            return 'exit_focus'

        logger.info("[TIME_STRATEGY] Neutral mode.")
        return 'neutral'

    except Exception as e:
        logger.error(f"[TIME_STRATEGY] Error determining mode: {e}")
        return 'neutral'

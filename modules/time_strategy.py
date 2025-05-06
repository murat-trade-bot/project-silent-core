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


def get_current_strategy_mode() -> StrategyMode:
    """
    Returns the current strategy mode based on UTC time and configured rules:
      - auto_close on special closure dates (MM-DD format in settings.STRATEGY_CLOSURE_DATES)
      - aggressive during market open hours
      - passive during late/night hours
      - defensive on Mondays
      - volatility_focus on Fridays
      - weekend_mode on Saturday/Sunday
      - entry_focus first days of month
      - exit_focus end of month days
      - neutral otherwise
    """
    try:
        now = datetime.utcnow()
        month_day = now.strftime('%m-%d')
        weekday = now.weekday()
        hour = now.hour
        day = now.day

        # Auto-close on special dates
        if month_day in SPECIAL_CLOSURE_DATES:
            return 'auto_close'

        # Market open aggressive window
        open_start, open_end = getattr(settings, 'AGGRESSIVE_HOURS', (8, 10))
        if open_start <= hour < open_end:
            return 'aggressive'

        # Nighttime passive window
        passive_start, passive_end = getattr(settings, 'PASSIVE_HOURS', (22, 2))
        # handle wrap-around midnight
        if passive_start <= hour or hour < passive_end:
            return 'passive'

        # Weekday rules
        if weekday == 0:
            return 'defensive'
        if weekday == 4:
            return 'volatility_focus'
        if weekday in (5, 6):
            return 'weekend_mode'

        # Day of month rules
        entry_limit = getattr(settings, 'ENTRY_FOCUS_DAY_END', 5)
        exit_start = getattr(settings, 'EXIT_FOCUS_DAY_START', 25)
        if day <= entry_limit:
            return 'entry_focus'
        if day >= exit_start:
            return 'exit_focus'

        # Default
        return 'neutral'

    except Exception as e:
        logger.error(f"[TIME_STRATEGY] Error determining mode: {e}")
        return 'neutral'

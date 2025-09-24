"""Compatibility shim mapping old imports to the new unified logger.

Any legacy code performing:
    from modules.logger import BotLogger
will transparently receive the singleton logger defined in core.logger.
"""
from core.logger import logger, get_logger, BotLogger

__all__ = ["logger", "get_logger", "BotLogger"]

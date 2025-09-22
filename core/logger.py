"""
Core logging adapter to provide a unified BotLogger() across the codebase.
Compatible with existing imports: `from core.logger import BotLogger` then `logger = BotLogger()`.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOGGER_NAME = "silent_core_bot"
_LOG_DIR = os.path.join(os.getcwd(), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "bot.log")
_SETUP_DONE = False


def _setup_logger(level=logging.INFO):
    global _SETUP_DONE
    if _SETUP_DONE:
        return logging.getLogger(_LOGGER_NAME)

    os.makedirs(_LOG_DIR, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

    # Rotating file handler
    fh = RotatingFileHandler(_LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'))

    # Avoid duplicate handlers
    logger.handlers.clear()
    logger.addHandler(ch)
    logger.addHandler(fh)

    _SETUP_DONE = True
    return logger


def BotLogger(level=logging.INFO) -> logging.Logger:
    """Factory returning the configured logger instance."""
    return _setup_logger(level)


def log_event(event: str, level: str = 'info', **kwargs):
    logger = BotLogger()
    msg = event
    if kwargs:
        msg += ' | ' + ', '.join(f'{k}={v}' for k, v in kwargs.items())
    if level == 'debug':
        logger.debug(msg)
    elif level == 'warning':
        logger.warning(msg)
    elif level == 'error':
        logger.error(msg)
    else:
        logger.info(msg)

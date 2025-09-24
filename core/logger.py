from __future__ import annotations
"""Unified logging module providing a singleton logger across the codebase.

Features:
 - Singleton logger (console + rotating file handler)
 - Backward compatible BotLogger() factory
 - Dynamic level change via set_level()
 - Exception logging decorator (log_exceptions)
 - Environment driven config (LOG_LEVEL, LOG_DIR)
"""
import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from typing import Optional, Callable, Any, TypeVar, cast

_DEFAULT_LOGGER_NAME = "silent_core"
_LOG_DIR_ENV = "LOG_DIR"
_LOG_FILE_NAME = "bot.log"
_DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_DIR = os.getenv(_LOG_DIR_ENV, "logs")

__logger_lock = threading.Lock()
__logger_singleton: Optional[logging.Logger] = None


def _ensure_logs_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:  # pragma: no cover - defensive
        pass


def _level_from_str(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


def get_logger(name: str = _DEFAULT_LOGGER_NAME) -> logging.Logger:
    """Return singleton logger instance."""
    global __logger_singleton
    if __logger_singleton:
        return __logger_singleton

    with __logger_lock:
        if __logger_singleton:
            return __logger_singleton

        logger = logging.getLogger(name)
        logger.setLevel(_level_from_str(_DEFAULT_LEVEL))
        logger.propagate = False

        if not logger.handlers:
            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(_level_from_str(_DEFAULT_LEVEL))
            ch.setFormatter(logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            logger.addHandler(ch)

            # File handler
            try:
                _ensure_logs_dir(_LOG_DIR)
                fh = RotatingFileHandler(
                    filename=os.path.join(_LOG_DIR, _LOG_FILE_NAME),
                    maxBytes=2 * 1024 * 1024,
                    backupCount=5,
                    encoding="utf-8"
                )
                fh.setLevel(_level_from_str(_DEFAULT_LEVEL))
                fh.setFormatter(logging.Formatter(
                    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                ))
                logger.addHandler(fh)
            except Exception:  # pragma: no cover
                pass

        __logger_singleton = logger
        return __logger_singleton


def set_level(level_name: str) -> None:
    logger = get_logger()
    lvl = _level_from_str(level_name)
    logger.setLevel(lvl)
    for h in logger.handlers:
        h.setLevel(lvl)


F = TypeVar("F", bound=Callable[..., Any])


def log_exceptions(context: str = "") -> Callable[[F], F]:
    def decorator(func: F) -> F:
        import functools
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                get_logger().exception("Unhandled exception%s", f" [{context}]" if context else "")
                raise
        return cast(F, wrapper)
    return decorator


class BotLogger:
    """Backward compatibility facade returning singleton logger."""
    def __new__(cls, *args, **kwargs):
        return get_logger()

    @staticmethod
    def setup(name: str = _DEFAULT_LOGGER_NAME) -> logging.Logger:
        return get_logger(name)


# Public alias
logger = get_logger()

__all__ = [
    "logger",
    "get_logger",
    "BotLogger",
    "set_level",
    "log_exceptions",
]

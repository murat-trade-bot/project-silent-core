from __future__ import annotations
import os
from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    SIM = "SIM"
    LIVE = "LIVE"


@dataclass
class RuntimeConfig:
    mode: Mode
    testnet: bool
    notifier_enabled: bool


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def load_runtime_config() -> RuntimeConfig:
    mode = os.getenv("EXECUTION_MODE", "SIM").upper()
    if mode not in ("SIM", "LIVE"):
        mode = "SIM"
    return RuntimeConfig(
        mode=Mode(mode),
        testnet=_bool_env("TESTNET_MODE", False),
        notifier_enabled=_bool_env("NOTIFIER_ENABLED", False),
    )


def assert_live_prereqs():
    """
    LIVE modda çalışmadan önce zorunlu anahtarlar ve spot-only önlemler.
    """
    missing = []
    if not os.getenv("BINANCE_API_KEY"):
        missing.append("BINANCE_API_KEY")
    if not os.getenv("BINANCE_API_SECRET"):
        missing.append("BINANCE_API_SECRET")
    if missing:
        raise ValueError(f"Missing LIVE credentials: {', '.join(missing)}")

    # Spot-only hatırlatıcı (futures/leverage kullanılmıyor)
    # İstenirse ek kontrol/guard eklenebilir.

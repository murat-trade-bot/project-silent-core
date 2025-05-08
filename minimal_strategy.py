# minimal_strategy.py

from typing import Dict

class Strategy:
    """
    Çok basit stub: her zaman HOLD döner.
    """
    def get_action(self, state: Dict) -> str:
        return "HOLD"

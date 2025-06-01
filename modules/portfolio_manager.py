"""
Portfolio Manager Module
Portföy dağılımını, varlık çeşitliliğini ve dönemsel hedeflere göre risk yönetimini sağlar.
Stealth mod, loglama ve 6 dönemlik kazanç planı ile tam uyumludur.
"""

import random
import time
from core.logger import BotLogger
from config import settings

logger = BotLogger()

class PortfolioManager:
    def __init__(self):
        self.target_allocation = {
            "BTC": 0.4,
            "ETH": 0.3,
            "BNB": 0.1,
            "STABLE": 0.2
        }
        self.assets = ["BTC", "ETH", "BNB", "USDT", "USDC"]
        self.period_multiplier = 1.0  # Dönem katsayısı, period_manager'dan alınabilir

    def get_current_portfolio(self, fetch_balances_func):
        """
        Güncel portföy bakiyelerini dışarıdan verilen fonksiyon ile çeker.
        """
        try:
            time.sleep(random.uniform(0.2, 0.8))  # Stealth mod
            balances = fetch_balances_func(self.assets)
            logger.info(f"PortfolioManager: Güncel portföy: {balances}")
            return balances
        except Exception as e:
            logger.error(f"PortfolioManager: Portföy çekilemedi: {e}")
            return {a: 0 for a in self.assets}

    def rebalance_portfolio(self, balances, total_balance):
        """
        Portföyü hedef dağılıma göre yeniden dengeler.
        """
        actions = []
        for asset, target_ratio in self.target_allocation.items():
            current = balances.get(asset, 0)
            target = total_balance * target_ratio * self.period_multiplier
            diff = target - current
            if abs(diff) / (total_balance + 1e-8) > 0.02:  # %2'den fazla sapma varsa
                action = "BUY" if diff > 0 else "SELL"
                actions.append({"asset": asset, "action": action, "amount": abs(diff)})
                logger.info(f"PortfolioManager: {action} {abs(diff):.2f} {asset} (hedef: {target:.2f}, mevcut: {current:.2f})")
        return actions

    def update_allocation_for_period(self, period_number):
        """
        Dönemsel hedeflere göre portföy dağılımını günceller.
        """
        # Örnek: Son dönemlerde stablecoin oranı artırılabilir
        if period_number >= 5:
            self.target_allocation["STABLE"] = 0.4
            self.target_allocation["BTC"] = 0.3
            self.target_allocation["ETH"] = 0.2
            self.target_allocation["BNB"] = 0.1
        logger.info(f"PortfolioManager: Yeni hedef dağılım: {self.target_allocation}")
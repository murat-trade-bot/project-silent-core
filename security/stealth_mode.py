import random
import time
from config import settings
from core.logger import BotLogger

logger = BotLogger()

class StealthMode:
    def __init__(self):
        self.drop_chance = settings.STEALTH_DROP_CHANCE
        self.sleep_chance = settings.STEALTH_SLEEP_CHANCE
        self.sleep_min = settings.STEALTH_SLEEP_MIN
        self.sleep_max = settings.STEALTH_SLEEP_MAX
        self.size_jitter = settings.STEALTH_ORDER_SIZE_JITTER

    def maybe_drop_trade(self):
        if random.random() < self.drop_chance:
            logger.log("[STEALTH] İşlem iptal edildi (drop).", level="WARNING")
            return True
        return False

    def maybe_enter_sleep(self):
        # Uyutmayı tamamen devre dışı bırakmak için settings.STEALTH_SLEEP_CHANCE = 0 yapılabilir
        if self.sleep_chance <= 0:
            return
        if random.random() < self.sleep_chance:
            d = random.randint(self.sleep_min, self.sleep_max)
            logger.log(f"[STEALTH] Botu uyutuyoruz: {d} sn", level="INFO")
            # Uyutma satırı yoruma alındı:
            # time.sleep(d)

    def apply_order_size_jitter(self, original_size: float):
        """
        Emir boyutuna jitter ekler:
        jitter_percent, -size_jitter ile +size_jitter arasında random seçilir.
        """
        jitter_percent = random.uniform(-self.size_jitter, self.size_jitter)
        new_size = original_size * (1 + jitter_percent)
        return round(new_size, 8)

    def dynamic_optimize(self, current_load):
        self.drop_chance = min(0.3, settings.STEALTH_DROP_CHANCE + current_load * 0.01)
        return self.drop_chance

stealth = StealthMode()

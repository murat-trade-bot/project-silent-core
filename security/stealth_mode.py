import random
import time
from config import settings

class StealthMode:
    def __init__(self):
        self.drop_chance = settings.STEALTH_DROP_CHANCE
        self.sleep_chance = settings.STEALTH_SLEEP_CHANCE
        self.sleep_min = settings.STEALTH_SLEEP_MIN
        self.sleep_max = settings.STEALTH_SLEEP_MAX
        self.size_jitter = settings.STEALTH_ORDER_SIZE_JITTER

    def maybe_drop_trade(self):
        if random.random() < self.drop_chance:
            print("[STEALTH] İşlem iptal edildi (drop).")
            return True
        return False

    def maybe_enter_sleep(self):
        if random.random() < self.sleep_chance:
            d = random.randint(self.sleep_min, self.sleep_max)
            print(f"[STEALTH] Botu uyutuyoruz: {d} sn")
            time.sleep(d)

    def apply_order_size_jitter(self, original_size: float):
        delta = original_size * self.size_jitter
        new_size = random.uniform(original_size - delta, original_size + delta)
        return round(new_size, 8)

    def dynamic_optimize(self, current_load):
        self.drop_chance = min(0.3, settings.STEALTH_DROP_CHANCE + current_load * 0.01)
        return self.drop_chance

stealth = StealthMode() 
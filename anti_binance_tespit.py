import random
import time
import requests
from config import settings
from core.logger import BotLogger

logger = BotLogger()

class AntiDetectionSystem:
    def __init__(self):
        self.last_request_time = 0
        self.request_count = 0
        self.max_requests_per_minute = 1200  # Binance rate limit
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
        self.proxy_list = []
        self.current_proxy_index = 0

        # Load proxies if enabled
        if settings.USE_PROXY:
            self.load_proxies()

    def load_proxies(self):
        """Proxy listesini internetten veya dosyadan yükler"""
        try:
            if settings.PROXY_LIST_PATH:
                with open(settings.PROXY_LIST_PATH, "r") as f:
                    self.proxy_list = [line.strip() for line in f if line.strip()]
                    logger.log(f"[ANTI] {len(self.proxy_list)} proxy yüklendi (dosyadan)")
            else:
                response = requests.get(
                    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
                    "&timeout=10000&country=all&ssl=all&anonymity=all",
                    timeout=settings.PROXY_TIMEOUT
                )
                if response.status_code == 200:
                    self.proxy_list = [
                        line.strip() for line in response.text.split('\n') if line.strip()
                    ]
                    logger.log(f"[ANTI] {len(self.proxy_list)} proxy yüklendi (online)")
        except Exception as e:
            logger.log(f"[ANTI] Proxy yükleme hatası: {e}", level="ERROR")

    def get_next_proxy(self):
        """Bir sonraki proxy'yi döndürür, yoksa uyarı verir"""
        if not settings.USE_PROXY or not self.proxy_list:
            logger.log("[ANTI] Proxy listesi boş veya kullanım dışı.", level="WARNING")
            return None
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def get_random_user_agent(self):
        """Rastgele bir User-Agent döndürür"""
        return random.choice(self.user_agents)

    def check_rate_limit(self):
        """Rate limit kontrolü yapar"""
        current_time = time.time()
        if current_time - self.last_request_time < 60:
            self.request_count += 1
            if self.request_count >= self.max_requests_per_minute:
                sleep_time = 60 - (current_time - self.last_request_time)
                logger.log(f"[ANTI] Rate limit aşıldı, {sleep_time:.2f} saniye bekleniyor", level="WARNING")
                time.sleep(sleep_time)
                self.request_count = 0
                self.last_request_time = time.time()
        else:
            self.request_count = 1
            self.last_request_time = current_time

    def add_jitter(self, value, jitter_percent=0.05):
        """Değere rastgele jitter ekler"""
        jitter = value * jitter_percent
        return value + random.uniform(-jitter, jitter)

    def randomize_order_size(self, size):
        """Emir boyutunu rastgele değiştirir"""
        return self.add_jitter(size)

    def randomize_price(self, price):
        """Fiyatı rastgele değiştirir"""
        return self.add_jitter(price, 0.001)

    def should_drop_request(self):
        """Bazı istekleri rastgele düşürür"""
        return random.random() < settings.STEALTH_DROP_CHANCE

# Global instance
anti_detection = AntiDetectionSystem()

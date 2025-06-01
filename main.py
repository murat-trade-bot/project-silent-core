from dotenv import load_dotenv
load_dotenv()
from binance.client import Client
from notifier import send_notification
import sys
import time
from config import settings
from core.logger import BotLogger
from core.engine import BotEngine
from modules.strategy_optimizer import optimize_strategy_parameters

logger = BotLogger()

def initialize_client(retries: int = 3, delay: int = 5) -> Client:
    """
    Binance Client'ı tekrar deneyerek başlatır, başarısız olursa bildirir ve çıkar.
    """
    for attempt in range(1, retries + 1):
        try:
            client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
            if getattr(settings, "TESTNET_MODE", False):
                client.API_URL = 'https://testnet.binance.vision/api'
                logger.info("Testnet mode enabled")
            else:
                logger.info("Live mode enabled")
            return client
        except Exception as e:
            logger.error(f"Client initialization failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                err_msg = f"Failed to initialize Binance client after {retries} attempts: {e}"
                logger.critical(err_msg)
                if getattr(settings, "NOTIFIER_ENABLED", False):
                    send_notification(f"[CRITICAL] {err_msg}")
                sys.exit(1)

def main():
    """
    Botun giriş noktası: client başlatılır, strateji optimize edilir ve ana döngü başlatılır.
    """
    client = initialize_client()

    try:
        optimize_strategy_parameters()
    except Exception as e:
        logger.warning(f"Strategy optimization failed: {e}")

    engine = BotEngine(client)
    try:
        engine.run()
    except Exception as e:
        logger.critical(f"Engine crashed: {e}")
        if getattr(settings, "NOTIFIER_ENABLED", False):
            send_notification(f"[CRITICAL] Engine crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

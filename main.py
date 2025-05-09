from dotenv import load_dotenv
from binance.client import Client
from notifier import send_notification
import sys
import time                

from config import settings
from core.logger import BotLogger
from core.engine import BotEngine
from modules.period_manager import start_period
from modules.strategy_optimizer import optimize_strategy_parameters

# Load environment variables
load_dotenv()
logger = BotLogger()

def initialize_client(retries: int = 3, delay: int = 5) -> Client:
    """
    Initialize the Binance Client with retry and notification.
    Attempts to connect up to `retries` times, waiting `delay` seconds between attempts.
    Sends a Telegram notification on persistent failure.
    """
    for attempt in range(1, retries + 1):
        try:
            client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
            if settings.TESTNET_MODE:
                client.API_URL = 'https://testnet.binance.vision/api'
                logger.info("Testnet mode enabled")
            else:
                logger.info("Live mode enabled")
            return client
        except Exception as e:
            logger.error(f"Client initialization failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time_msg = f"Retrying in {delay} seconds..."
                logger.info(time_msg)
                time.sleep(delay)
            else:
                err_msg = f"Failed to initialize Binance client after {retries} attempts: {e}"
                logger.critical(err_msg)
                if settings.NOTIFIER_ENABLED:
                    send_notification(f"[CRITICAL] {err_msg}")
                sys.exit(1)

def main():
    """
    Entry point for the bot: initialize client, start period, optimize strategy, and run engine.
    """
    client = initialize_client()
    # Initialize trading period state
    start_period(client)
    # Optional strategy optimization step
    optimize_strategy_parameters()
    # Create and run the core engine
    engine = BotEngine(client)
    engine.run()

if __name__ == "__main__":
    main()

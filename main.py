from dotenv import load_dotenv
from binance.client import Client

from config import settings
from core.logger import BotLogger
from core.engine import BotEngine
from modules.period_manager import start_period
from modules.strategy_optimizer import optimize_strategy_parameters

# Load environment variables
load_dotenv()
logger = BotLogger()

def initialize_client():
    """
    Initialize the Binance Client using API keys and testnet mode.
    """
    client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
    if settings.TESTNET_MODE:
        client.API_URL = 'https://testnet.binance.vision/api'
        logger.info("Testnet mode enabled")
    else:
        logger.info("Live mode enabled")
    return client

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

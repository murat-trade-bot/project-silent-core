import os
from dotenv import load_dotenv

load_dotenv()

SYMBOL = "BTCUSDT"
CYCLE_INTERVAL = 60
CYCLE_JITTER_MIN = -10
CYCLE_JITTER_MAX = 10

LOG_FILE = "bot_logs.txt"

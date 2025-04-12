import datetime
from config import settings

class BotLogger:
    def __init__(self, logfile=None):
        self.logfile = logfile or settings.LOG_FILE

    def log(self, message):
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now} UTC] {message}"
        print(line)
        with open(self.logfile, "a", encoding="utf-8") as f:
            f.write(line + "\n")

import datetime
import os
from config import settings

class BotLogger:
    def __init__(self, logfile=None):
        self.logfile = logfile or settings.LOG_FILE
        self.ensure_log_directory()

    def ensure_log_directory(self):
        """Log dosyasının bulunduğu klasör varsa yoksa oluşturur"""
        log_dir = os.path.dirname(self.logfile)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def log(self, message, level="INFO"):
        """Log mesajını hem konsola hem dosyaya yazar"""
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now} UTC] [{level}] {message}"
        print(line)
        try:
            with open(self.logfile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"[LOGGER] Dosyaya yazılamadı: {e}")

    def info(self, message):
        self.log(message, level="INFO")

    def warning(self, message):
        self.log(message, level="WARNING")

    def error(self, message):
        self.log(message, level="ERROR")

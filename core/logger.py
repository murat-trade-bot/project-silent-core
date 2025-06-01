import os
import datetime
import time
import requests
from config import settings

class BotLogger:
    def __init__(self, logfile=None):
        self.logfile = logfile or settings.LOG_FILE
        self.ensure_log_directory()
        self.cleanup_old_logs()

    def ensure_log_directory(self):
        """
        Ensure the directory for the log file exists.
        """
        log_dir = os.path.dirname(self.logfile)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def cleanup_old_logs(self):
        """
        Delete log files older than 7 days in the log directory.
        Only files ending with .log or .txt are deleted.
        """
        log_dir = os.path.dirname(self.logfile) or '.'
        now = time.time()
        for filename in os.listdir(log_dir):
            if not (filename.endswith('.log') or filename.endswith('.txt')):
                continue
            file_path = os.path.join(log_dir, filename)
            if os.path.isfile(file_path) and os.stat(file_path).st_mtime < now - 7 * 86400:
                try:
                    os.remove(file_path)
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [LOGGER] Deleted old log file: {filename}")
                except Exception as e:
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [LOGGER] Failed to delete {filename}: {e}")

    def log(self, message, level="INFO"):
        """
        Write a log message with timestamp and level to console and file.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"
        print(line)
        try:
            with open(self.logfile, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception as e:
            err_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{err_time}] [LOGGER] Failed to write to log file: {e}")

    def info(self, message):
        self.log(message, level="INFO")

    def warning(self, message):
        self.log(message, level="WARNING")

    def error(self, message):
        self.log(message, level="ERROR")

    def critical(self, message):
        self.log(message, level="CRITICAL")

    def send_telegram_alert(self, message):
        """
        Send an alert message to Telegram using bot token and chat ID from settings.
        """
        try:
            token = getattr(settings, "TELEGRAM_TOKEN", None)
            chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
            if not token or not chat_id:
                self.error("Telegram token or chat_id not set in settings.")
                return
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {"chat_id": chat_id, "text": message}
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                self.error(f"Telegram alert failed: {response.text}")
        except Exception as e:
            self.error(f"Telegram alert exception: {e}")

    def exception(self, msg):
        import traceback
        self.error(f"{msg}\n{traceback.format_exc()}")

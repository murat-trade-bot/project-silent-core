import os
import datetime
import time
from config import settings

class BotLogger:
    def __init__(self, logfile=None):
        self.logfile = logfile or settings.LOG_FILE
        self.ensure_log_directory()
        # Clean up old logs once at startup
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
        """
        log_dir = os.path.dirname(self.logfile) or '.'
        now = time.time()
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            if os.path.isfile(file_path) and os.stat(file_path).st_mtime < now - 7 * 86400:
                try:
                    os.remove(file_path)
                    # Inform via console only
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [LOGGER] "
                          f"Deleted old log file: {filename}")
                except Exception as e:
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"[LOGGER] Failed to delete {filename}: {e}")

    def log(self, message, level="INFO"):
        """
        Write a log message with timestamp and level to console and file.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"
        # Print to console
        print(line)
        # Append to log file
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

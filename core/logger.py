import datetime
import os
import time            # ← zaman kontrolü için
from config import settings

class BotLogger:
    def __init__(self, logfile=None):
        self.logfile = logfile or settings.LOG_FILE
        self.ensure_log_directory()
        self.cleanup_old_logs()  # ← Başlangıçta eski logları temizle

    def ensure_log_directory(self):
        """Log dosyasının bulunduğu klasör varsa yoksa oluşturur"""
        log_dir = os.path.dirname(self.logfile)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def cleanup_old_logs(self):
        """
        Log klasöründeki 7 günden eski dosyaları siler.
        """
        log_dir = os.path.dirname(self.logfile) or "."
        now = time.time()
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            if os.path.isfile(file_path) and os.stat(file_path).st_mtime < now - 7 * 86400:
                try:
                    os.remove(file_path)
                    # Silme bilgisini logla
                    self.log(f"Eski log dosyası temizlendi: {filename}", level="INFO")
                except Exception as e:
                    # Temizleme hatasını da logla
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [LOGGER] "
                          f"Eski log temizlenemedi ({filename}): {e}")

    def log(self, message, level="INFO"):
        """Log mesajını hem konsola hem dosyaya yazar (yerel saat dilimi)"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] [{level}] {message}"
        print(line)
        try:
            with open(self.logfile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            err_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{err_time}] [LOGGER] Dosyaya yazılamadı: {e}")

    def info(self, message):
        self.log(message, level="INFO")

    def warning(self, message):
        self.log(message, level="WARNING")

    def error(self, message):
        self.log(message, level="ERROR")

# logger.py
"""
Detaylı ve merkezi loglama sistemi
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class BotLogger:
    @staticmethod
    def setup(log_file: str = LOG_FILE, level=logging.INFO):
        logger = logging.getLogger()
        logger.setLevel(level)
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch_fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        ch.setFormatter(ch_fmt)
        # File handler (rotating)
        fh = RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=5)
        fh.setLevel(level)
        fh_fmt = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s')
        fh.setFormatter(fh_fmt)
        # Add handlers if not already
        if not logger.handlers:
            logger.addHandler(ch)
            logger.addHandler(fh)
        else:
            logger.handlers.clear()
            logger.addHandler(ch)
            logger.addHandler(fh)
        return logger

    @staticmethod
    def get_logger():
        return logging.getLogger()

# Kısa log fonksiyonu
def log_event(event: str, level: str = 'info', **kwargs):
    logger = logging.getLogger()
    msg = event
    if kwargs:
        msg += ' | ' + ', '.join(f'{k}={v}' for k, v in kwargs.items())
    if level == 'info':
        logger.info(msg)
    elif level == 'warning':
        logger.warning(msg)
    elif level == 'error':
        logger.error(msg)
    elif level == 'debug':
        logger.debug(msg)
    else:
        logger.info(msg)

# Test fonksiyonu
def test_logger():
    BotLogger.setup()
    log_event('Sinyal üretildi', symbol='BTCUSDT', signal='BUY')
    log_event('Emir gönderildi', level='info', symbol='BTCUSDT', qty=0.01)
    log_event('Hata oluştu', level='error', error='API timeout')
    log_event('Kâr limiti aşıldı', level='warning', profit_pct=4.2)

if __name__ == "__main__":
    test_logger()

import os
import time
import random
import csv
import ssl
import requests
import asyncio
import concurrent.futures
import logging
import json
import hashlib
import hmac
import base64
import yaml
import jsonschema
import gc
import psutil
import weakref
import resource
import ntplib
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Union, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, Timeout, ConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache, cached
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from logging import Formatter
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from contextlib import contextmanager
from queue import Queue, PriorityQueue
from threading import Lock, Event, Thread
from concurrent.futures import ThreadPoolExecutor
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

from config import settings
from core.logger import BotLogger
from core.strategy import Strategy
from core.executor import ExecutorManager
from modules.time_strategy import get_current_strategy_mode
from modules.global_risk_index import GlobalRiskAnalyzer
from smart_entry.orderbook_analyzer import OrderBookAnalyzer
from security.stealth_mode import stealth
from modules.technical_analysis import (
    fetch_ohlcv_from_binance, calculate_rsi,
    calculate_macd, calculate_atr
)
from modules.sentiment_analysis import analyze_sentiment
from modules.onchain_tracking import track_onchain_activity
from modules.dynamic_position import get_dynamic_position_size
from modules.strategy_optimizer import optimize_strategy_parameters
from modules.domino_effect import detect_domino_effect
from modules.multi_asset_selector import select_coins
from modules.performance_optimization import optimize_performance_infrastructure
from modules.period_manager import update_settings_for_period, perform_period_withdrawal
from notifier import send_notification

# Konfigürasyon Yönetimi Sınıfları
class ConfigManager:
    """Konfigürasyon yönetimi"""
    def __init__(self):
        self.config_dir = Path('config')
        self.config_files = {
            'settings': self.config_dir / 'settings.yaml',
            'strategy': self.config_dir / 'strategy.yaml',
            'security': self.config_dir / 'security.yaml'
        }
        self.schemas = self._load_schemas()
        self.configs = {}
        self.last_modified = {}
        self.observer = None
        self._setup_file_watcher()

    def _load_schemas(self) -> Dict:
        """JSON şemalarını yükle"""
        return {
            'settings': {
                'type': 'object',
                'required': ['API_KEY', 'API_SECRET', 'SYMBOLS', 'TARGET_USDT'],
                'properties': {
                    'API_KEY': {'type': 'string', 'minLength': 64, 'maxLength': 64},
                    'API_SECRET': {'type': 'string', 'minLength': 64, 'maxLength': 64},
                    'SYMBOLS': {'type': 'array', 'items': {'type': 'string'}},
                    'TARGET_USDT': {'type': 'number', 'minimum': 0}
                }
            },
            'strategy': {
                'type': 'object',
                'required': ['TAKE_PROFIT_RATIO', 'STOP_LOSS_RATIO'],
                'properties': {
                    'TAKE_PROFIT_RATIO': {'type': 'number', 'minimum': 0},
                    'STOP_LOSS_RATIO': {'type': 'number', 'minimum': 0}
                }
            },
            'security': {
                'type': 'object',
                'required': ['IP_WHITELIST', 'MAX_FAILED_ATTEMPTS'],
                'properties': {
                    'IP_WHITELIST': {'type': 'array', 'items': {'type': 'string'}},
                    'MAX_FAILED_ATTEMPTS': {'type': 'integer', 'minimum': 1}
                }
            }
        }

    def _setup_file_watcher(self) -> None:
        """Dosya değişikliklerini izle"""
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager

            def on_modified(self, event):
                if event.src_path in self.manager.config_files.values():
                    self.manager.reload_config(Path(event.src_path).name)

        self.observer = Observer()
        self.observer.schedule(
            ConfigFileHandler(self),
            str(self.config_dir),
            recursive=False
        )
        self.observer.start()

    def load_all_configs(self) -> None:
        """Tüm konfigürasyon dosyalarını yükle"""
        for name, path in self.config_files.items():
            self.load_config(name)

    def load_config(self, config_name: str) -> None:
        """Belirli bir konfigürasyon dosyasını yükle"""
        try:
            path = self.config_files[config_name]
            if not path.exists():
                raise ConfigurationError(f"Konfigürasyon dosyası bulunamadı: {path}")

            with open(path, 'r') as f:
                config = yaml.safe_load(f)
                self._validate_config(config, config_name)
                self.configs[config_name] = config
                self.last_modified[config_name] = path.stat().st_mtime
                logger.logger.info(f"Konfigürasyon yüklendi: {config_name}")

        except Exception as e:
            logger.log_error(e, {"config_name": config_name})
            raise ConfigurationError(f"Konfigürasyon yüklenemedi: {config_name}")

    def reload_config(self, config_name: str) -> None:
        """Konfigürasyon dosyasını yeniden yükle"""
        try:
            path = self.config_files[config_name]
            current_mtime = path.stat().st_mtime
            
            if current_mtime > self.last_modified.get(config_name, 0):
                self.load_config(config_name)
                logger.logger.info(f"Konfigürasyon yeniden yüklendi: {config_name}")
                
                if settings.NOTIFIER_ENABLED:
                    send_notification(f"Konfigürasyon güncellendi: {config_name}")
        except Exception as e:
            logger.log_error(e, {"config_name": config_name})

    def _validate_config(self, config: Dict, config_name: str) -> None:
        """Konfigürasyonu doğrula"""
        try:
            jsonschema.validate(instance=config, schema=self.schemas[config_name])
        except jsonschema.exceptions.ValidationError as e:
            raise ConfigurationError(f"Geçersiz konfigürasyon formatı ({config_name}): {e}")

    def get_config(self, config_name: str, key: str, default: Any = None) -> Any:
        """Konfigürasyon değerini al"""
        try:
            return self.configs[config_name].get(key, default)
        except KeyError:
            return default

    def update_config(self, config_name: str, key: str, value: Any) -> None:
        """Konfigürasyon değerini güncelle"""
        try:
            if config_name not in self.configs:
                self.configs[config_name] = {}
            
            self.configs[config_name][key] = value
            self._validate_config(self.configs[config_name], config_name)
            
            # Dosyaya kaydet
            with open(self.config_files[config_name], 'w') as f:
                yaml.dump(self.configs[config_name], f)
            
            logger.logger.info(f"Konfigürasyon güncellendi: {config_name}.{key}")
        except Exception as e:
            logger.log_error(e, {"config_name": config_name, "key": key})
            raise ConfigurationError(f"Konfigürasyon güncellenemedi: {config_name}.{key}")

    def cleanup(self) -> None:
        """Kaynakları temizle"""
        if self.observer:
            self.observer.stop()
            self.observer.join()

class ConfigurationError(Exception):
    """Konfigürasyon hatası"""
    pass

# Konfigürasyon yöneticisini başlat
config_manager = ConfigManager()
config_manager.load_all_configs()

# Gelişmiş Loglama Sistemi
class EnhancedLogger:
    """Gelişmiş loglama sistemi"""
    def __init__(self):
        self.logger = logging.getLogger('trading_bot')
        self.logger.setLevel(logging.DEBUG)
        
        # Konsol handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Dosya handler (günlük rotasyon)
        file_handler = TimedRotatingFileHandler(
            'logs/trading_bot.log',
            when='midnight',
            interval=1,
            backupCount=7
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Hata logları için ayrı dosya
        error_handler = RotatingFileHandler(
            'logs/errors.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s\n%(exc_info)s')
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
        
        # Performans metrikleri için JSON log
        self.metrics_logger = logging.getLogger('metrics')
        metrics_handler = TimedRotatingFileHandler(
            'logs/metrics.json',
            when='midnight',
            interval=1,
            backupCount=7
        )
        metrics_handler.setLevel(logging.INFO)
        self.metrics_logger.addHandler(metrics_handler)

    def log_trade(self, trade_data: Dict) -> None:
        """İşlem logunu kaydet"""
        self.logger.info(f"İşlem: {json.dumps(trade_data, default=str)}")

    def log_error(self, error: Exception, context: Dict = None) -> None:
        """Hata logunu kaydet"""
        error_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context
        }
        self.logger.error(json.dumps(error_data))

    def log_metric(self, metric_name: str, value: Any) -> None:
        """Performans metriğini kaydet"""
        metric_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'metric': metric_name,
            'value': value
        }
        self.metrics_logger.info(json.dumps(metric_data))

    def log_debug(self, message: str, data: Dict = None) -> None:
        """Debug logunu kaydet"""
        if settings.DEBUG_MODE:
            debug_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'message': message,
                'data': data
            }
            self.logger.debug(json.dumps(debug_data))

# Loglama sistemini başlat
logger = EnhancedLogger()

# Hata İzleme Sistemi
class ErrorTracker:
    """Hata izleme ve raporlama sistemi"""
    def __init__(self):
        self.error_counts = {}
        self.last_error_time = {}
        self.error_threshold = 5  # Belirli bir sürede maksimum hata sayısı
        self.time_window = 300  # 5 dakika

    def track_error(self, error_type: str) -> None:
        """Hatayı izle ve raporla"""
        current_time = time.time()
        
        # Hata sayısını güncelle
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
            self.last_error_time[error_type] = current_time
        
        self.error_counts[error_type] += 1
        
        # Eğer son hata zamanından bu yana time_window geçtiyse sıfırla
        if current_time - self.last_error_time[error_type] > self.time_window:
            self.error_counts[error_type] = 1
            self.last_error_time[error_type] = current_time
        
        # Hata eşiğini aştıysa uyarı gönder
        if self.error_counts[error_type] >= self.error_threshold:
            message = f"Kritik hata eşiği aşıldı: {error_type} - Son {self.time_window} saniyede {self.error_counts[error_type]} hata"
            logger.log_error(Exception(message))
            if settings.NOTIFIER_ENABLED:
                send_notification(message)

error_tracker = ErrorTracker()

# Performans İzleme Sistemi
class PerformanceMonitor:
    """Performans izleme ve optimizasyon"""
    def __init__(self):
        self.metrics = {
            'api_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'execution_times': [],
            'memory_usage': [],
            'errors': {}
        }
        self.start_time = time.time()
        self.last_metrics_time = time.time()
        self.metrics_interval = 60  # saniye

    def record_metric(self, metric_name: str, value: Any) -> None:
        """Metrik kaydet"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append({
            'timestamp': datetime.utcnow().isoformat(),
            'value': value
        })
        
        # Belirli aralıklarla metrikleri logla
        current_time = time.time()
        if current_time - self.last_metrics_time >= self.metrics_interval:
            self.log_metrics()
            self.last_metrics_time = current_time

    def log_metrics(self) -> None:
        """Metrikleri logla"""
        metrics_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime': time.time() - self.start_time,
            'api_calls_per_minute': self.metrics['api_calls'] / ((time.time() - self.start_time) / 60),
            'cache_hit_ratio': self.metrics['cache_hits'] / (self.metrics['cache_hits'] + self.metrics['cache_misses']) if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0,
            'average_execution_time': sum(self.metrics['execution_times']) / len(self.metrics['execution_times']) if self.metrics['execution_times'] else 0,
            'error_counts': self.metrics['errors']
        }
        logger.log_metric('performance', metrics_data)

    def record_error(self, error_type: str) -> None:
        """Hata kaydet"""
        if error_type not in self.metrics['errors']:
            self.metrics['errors'][error_type] = 0
        self.metrics['errors'][error_type] += 1
        error_tracker.track_error(error_type)

performance_monitor = PerformanceMonitor()

# Özel Exception sınıfları
class TradingBotError(Exception):
    """Temel hata sınıfı"""
    pass

class APIError(TradingBotError):
    """API ile ilgili hatalar"""
    pass

class DataValidationError(TradingBotError):
    """Veri doğrulama hataları"""
    pass

class ConfigurationError(TradingBotError):
    """Konfigürasyon hataları"""
    pass

@dataclass
class TradeResult:
    """İşlem sonucu veri yapısı"""
    symbol: str
    action: str
    quantity: Decimal
    price: Decimal
    pnl: Decimal
    timestamp: datetime
    duration: float

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeResult':
        """Dictionary'den TradeResult oluştur"""
        try:
            return cls(
                symbol=data['symbol'],
                action=data['action'],
                quantity=Decimal(str(data['quantity'])),
                price=Decimal(str(data['price'])),
                pnl=Decimal(str(data['pnl'])),
                timestamp=data['timestamp'],
                duration=float(data['duration'])
            )
        except (KeyError, ValueError) as e:
            raise DataValidationError(f"Geçersiz trade verisi: {e}")

logger = BotLogger()
executor = ExecutorManager()

# --- Başlangıç Ayarları ---
START_TIME = time.time()
HEARTBEAT_INTERVAL = 3600  # saniye
CSV_FILE = settings.CSV_LOG_FILE

# --- Orijinal Temel Pozisyon Boyutları ---
try:
    BASE_POSITION_PCT = Decimal(str(settings.POSITION_SIZE_PCT))
    BASE_TRADE_USDT_AMOUNT = Decimal(str(getattr(settings, "TRADE_USDT_AMOUNT", 0)))
except (ValueError, AttributeError) as e:
    raise ConfigurationError(f"Geçersiz pozisyon boyutu ayarları: {e}")

# --- İstatistik Değişkenleri ---
try:
    start_balance = Decimal(str(executor.get_balance('USDT')))
except Exception as e:
    raise APIError(f"Başlangıç bakiyesi alınamadı: {e}")

total_trades = 0
win_trades = 0
loss_trades = 0
trade_durations: List[float] = []
peak_balance = start_balance
max_drawdown = Decimal('0.0')

# Başlangıçta dönemi yükleyip loglayalım
period = update_settings_for_period()
logger.logger.info(f"[PERIOD] Başlangıçta Aktif dönem: {period['name']} | "
            f"Hedef={period['target_balance']:.2f} USDT | "
            f"TP={period['take_profit_ratio']:.2f} | "
            f"SL={period['stop_loss_ratio']:.2f} | "
            f"Growth={period['growth_factor']}")
print(f"Bot Başlatıldı:      {datetime.utcnow()} UTC")
print(f"Başlangıç Sermayesi: {start_balance:.2f} USDT")
print(f"Hedef Sermaye:       {settings.TARGET_USDT:.2f} USDT")

# Önbellek yapılandırması
class CacheManager:
    """Önbellek yönetimi"""
    def __init__(self):
        # OHLCV verisi için 5 dakikalık TTL
        self.ohlcv_cache = TTLCache(maxsize=100, ttl=300)
        # Teknik göstergeler için 1 dakikalık TTL
        self.indicators_cache = TTLCache(maxsize=200, ttl=60)
        # Bakiye bilgisi için 30 saniyelik TTL
        self.balance_cache = TTLCache(maxsize=10, ttl=30)

    def clear_all(self) -> None:
        """Tüm önbellekleri temizle"""
        self.ohlcv_cache.clear()
        self.indicators_cache.clear()
        self.balance_cache.clear()

cache_manager = CacheManager()

# Asenkron işlem yöneticisi
class AsyncManager:
    """Asenkron işlem yönetimi"""
    def __init__(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.loop = asyncio.get_event_loop()

    async def run_in_thread(self, func, *args, **kwargs):
        """Fonksiyonu thread pool'da çalıştır"""
        return await self.loop.run_in_executor(
            self.executor, 
            lambda: func(*args, **kwargs)
        )

    def shutdown(self):
        """Kaynakları temizle"""
        self.executor.shutdown(wait=True)
        self.loop.close()

async_manager = AsyncManager()

# Önbelleklenmiş fonksiyonlar
@cached(cache=TTLCache(maxsize=100, ttl=300))
def get_cached_ohlcv(symbol: str, interval: str, limit: int = 50) -> List[List[Union[int, float]]]:
    """Önbelleklenmiş OHLCV verisi"""
    return fetch_ohlcv_from_binance(symbol, interval, limit)

@cached(cache=TTLCache(maxsize=200, ttl=60))
def calculate_cached_indicators(prices: List[float]) -> Tuple[float, List[float], List[float]]:
    """Önbelleklenmiş teknik gösterge hesaplamaları"""
    rsi = calculate_rsi(prices)[-1] if prices else None
    macd, signal = calculate_macd(prices)
    return rsi, macd, signal

# Asenkron işlem fonksiyonları
async def fetch_ohlcv_async(symbol: str, interval: str, limit: int = 50) -> List[List[Union[int, float]]]:
    """Asenkron OHLCV verisi alma"""
    cache_key = f"{symbol}_{interval}_{limit}"
    if cache_key in cache_manager.ohlcv_cache:
        performance_monitor.record_cache_hit()
        return cache_manager.ohlcv_cache[cache_key]
    
    performance_monitor.record_cache_miss()
    data = await async_manager.run_in_thread(fetch_ohlcv_from_binance, symbol, interval, limit)
    cache_manager.ohlcv_cache[cache_key] = data
    return data

async def calculate_indicators_async(prices: List[float]) -> Tuple[float, List[float], List[float]]:
    """Asenkron teknik gösterge hesaplama"""
    cache_key = hash(tuple(prices))
    if cache_key in cache_manager.indicators_cache:
        performance_monitor.record_cache_hit()
        return cache_manager.indicators_cache[cache_key]
    
    performance_monitor.record_cache_miss()
    result = await async_manager.run_in_thread(calculate_cached_indicators, prices)
    cache_manager.indicators_cache[cache_key] = result
    return result

def validate_ohlcv_data(data: List, timeframe: str) -> None:
    """OHLCV verilerini doğrula"""
    if not data:
        raise DataValidationError(f"{timeframe} için OHLCV verisi boş")
    if len(data) < 2:
        raise DataValidationError(f"{timeframe} için yetersiz veri noktası")
    for candle in data:
        if len(candle) != 6:
            raise DataValidationError(f"Geçersiz OHLCV formatı: {candle}")

def log_trade_csv(trade: TradeResult) -> None:
    """
    İşlem kaydını CSV dosyasına ekle
    """
    try:
        fieldnames = ['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']
        exists = os.path.isfile(CSV_FILE)
        
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow({
                'timestamp': trade.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': trade.symbol,
                'action': trade.action,
                'quantity': str(trade.quantity),
                'price': str(trade.price),
                'pnl': str(trade.pnl)
            })
    except (IOError, csv.Error) as e:
        logger.logger.error(f"CSV yazma hatası: {e}")
        raise

# Güvenlik Sınıfları
class SecurityManager:
    """Güvenlik yönetimi"""
    def __init__(self):
        self.encryption_key = self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        self.api_key_salt = os.urandom(16)
        self.max_failed_attempts = 3
        self.failed_attempts = {}
        self.ip_whitelist = self._load_ip_whitelist()
        self.last_security_check = time.time()
        self.security_check_interval = 300  # 5 dakika

    def _generate_encryption_key(self) -> bytes:
        """Şifreleme anahtarı oluştur"""
        password = os.getenv('ENCRYPTION_PASSWORD', '').encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    def _load_ip_whitelist(self) -> List[str]:
        """IP beyaz listesini yükle"""
        try:
            with open('config/ip_whitelist.txt', 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def encrypt_data(self, data: str) -> bytes:
        """Veriyi şifrele"""
        return self.cipher_suite.encrypt(data.encode())

    def decrypt_data(self, encrypted_data: bytes) -> str:
        """Şifrelenmiş veriyi çöz"""
        return self.cipher_suite.decrypt(encrypted_data).decode()

    def verify_api_signature(self, data: Dict, signature: str) -> bool:
        """API imzasını doğrula"""
        try:
            message = json.dumps(data, sort_keys=True).encode()
            expected_signature = hmac.new(
                self.api_key_salt,
                message,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False

    def check_security_measures(self) -> None:
        """Güvenlik önlemlerini kontrol et"""
        current_time = time.time()
        if current_time - self.last_security_check >= self.security_check_interval:
            self._perform_security_checks()
            self.last_security_check = current_time

    def _perform_security_checks(self) -> None:
        """Güvenlik kontrollerini gerçekleştir"""
        try:
            # API anahtarlarının güvenliğini kontrol et
            self._check_api_keys()
            
            # Dosya sisteminin güvenliğini kontrol et
            self._check_file_permissions()
            
            # Ağ güvenliğini kontrol et
            self._check_network_security()
            
            # Bellek güvenliğini kontrol et
            self._check_memory_security()
            
            logger.logger.info("Güvenlik kontrolleri başarıyla tamamlandı")
        except Exception as e:
            logger.log_error(e, {"security_check": "failed"})
            if settings.NOTIFIER_ENABLED:
                send_notification(f"Güvenlik kontrolü hatası: {str(e)}")

    def _check_api_keys(self) -> None:
        """API anahtarlarının güvenliğini kontrol et"""
        required_keys = ['BINANCE_API_KEY', 'BINANCE_API_SECRET']
        for key in required_keys:
            if not os.getenv(key):
                raise SecurityError(f"API anahtarı eksik: {key}")
            if len(os.getenv(key)) != 64:
                raise SecurityError(f"Geçersiz API anahtarı formatı: {key}")

    def _check_file_permissions(self) -> None:
        """Dosya izinlerini kontrol et"""
        sensitive_files = [
            'config/settings.py',
            'logs/errors.log',
            'logs/metrics.json'
        ]
        for file in sensitive_files:
            if os.path.exists(file):
                mode = os.stat(file).st_mode
                if mode & 0o777 != 0o600:  # Sadece sahibi okuma/yazma
                    os.chmod(file, 0o600)
                    logger.logger.warning(f"Dosya izinleri düzeltildi: {file}")

    def _check_network_security(self) -> None:
        """Ağ güvenliğini kontrol et"""
        # SSL sertifikalarını kontrol et
        ssl_context = ssl.create_default_context()
        if not ssl_context.verify_mode == ssl.CERT_REQUIRED:
            raise SecurityError("SSL sertifika doğrulaması devre dışı")

    def _check_memory_security(self) -> None:
        """Bellek güvenliğini kontrol et"""
        # Hassas verilerin bellekten temizlendiğinden emin ol
        gc.collect()

class SecurityError(Exception):
    """Güvenlik hatası"""
    pass

# Güvenlik yöneticisini başlat
security_manager = SecurityManager()

# API Yapılandırması
class APIConfig:
    """API yapılandırma sınıfı"""
    def __init__(self):
        self.api_key = security_manager.decrypt_data(os.getenv('BINANCE_API_KEY').encode())
        self.api_secret = security_manager.decrypt_data(os.getenv('BINANCE_API_SECRET').encode())
        self.base_url = 'https://api.binance.com'
        self.rate_limit = 1200
        self.timeout = 10
        self.retry_attempts = 3
        self.retry_delay = 1

    def validate_credentials(self) -> None:
        """API kimlik bilgilerini doğrula"""
        if not self.api_key or not self.api_secret:
            raise SecurityError("API kimlik bilgileri eksik")
        if len(self.api_key) != 64 or len(self.api_secret) != 64:
            raise SecurityError("Geçersiz API kimlik bilgileri formatı")

# Kaynak Yönetimi Sınıfları
class ResourceManager:
    """Kaynak yönetimi"""
    def __init__(self):
        self.process = psutil.Process()
        self.memory_limit = self._get_memory_limit()
        self.connection_pool = ConnectionPool()
        self.file_handlers = {}
        self.locks = {}
        self.cleanup_queue = Queue()
        self._setup_resource_monitoring()

    def _get_memory_limit(self) -> int:
        """Bellek limitini al"""
        try:
            return resource.getrlimit(resource.RLIMIT_AS)[0]
        except (resource.error, AttributeError):
            return 1024 * 1024 * 1024  # 1GB varsayılan limit

    def _setup_resource_monitoring(self) -> None:
        """Kaynak izleme sistemini kur"""
        self.memory_threshold = self.memory_limit * 0.8  # %80 bellek kullanımı
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 dakika

    def check_resources(self) -> None:
        """Kaynak kullanımını kontrol et"""
        current_time = time.time()
        
        # Bellek kullanımını kontrol et
        memory_usage = self.process.memory_info().rss
        if memory_usage > self.memory_threshold:
            self._perform_cleanup()
            logger.logger.warning(f"Yüksek bellek kullanımı: {memory_usage / 1024 / 1024:.2f}MB")
        
        # Düzenli temizlik
        if current_time - self.last_cleanup >= self.cleanup_interval:
            self._perform_cleanup()
            self.last_cleanup = current_time

    def _perform_cleanup(self) -> None:
        """Kaynak temizliği yap"""
        try:
            # Bağlantı havuzunu temizle
            self.connection_pool.cleanup()
            
            # Dosya işleyicilerini kapat
            self._close_file_handlers()
            
            # Önbelleği temizle
            gc.collect()
            
            # Temizlik kuyruğunu işle
            while not self.cleanup_queue.empty():
                cleanup_func = self.cleanup_queue.get()
                try:
                    cleanup_func()
                except Exception as e:
                    logger.log_error(e, {"cleanup": "failed"})
            
            logger.logger.info("Kaynak temizliği tamamlandı")
        except Exception as e:
            logger.log_error(e, {"cleanup": "failed"})

    def _close_file_handlers(self) -> None:
        """Açık dosya işleyicilerini kapat"""
        for handler in self.file_handlers.values():
            try:
                handler.close()
            except Exception as e:
                logger.log_error(e, {"file_handler": "close_failed"})
        self.file_handlers.clear()

    @contextmanager
    def get_file_handler(self, file_path: str, mode: str = 'r') -> Any:
        """Dosya işleyicisi al"""
        if file_path not in self.file_handlers:
            self.file_handlers[file_path] = open(file_path, mode)
        try:
            yield self.file_handlers[file_path]
        finally:
            pass

    def get_lock(self, name: str) -> Lock:
        """Kilit nesnesi al"""
        if name not in self.locks:
            self.locks[name] = Lock()
        return self.locks[name]

    def register_cleanup(self, cleanup_func: callable) -> None:
        """Temizlik fonksiyonu kaydet"""
        self.cleanup_queue.put(cleanup_func)

    def cleanup(self) -> None:
        """Tüm kaynakları temizle"""
        self._perform_cleanup()
        self.connection_pool.close()
        self._close_file_handlers()

class ConnectionPool:
    """Bağlantı havuzu yönetimi"""
    def __init__(self):
        self.pool = {}
        self.max_size = 10
        self.timeout = 30
        self.last_used = {}

    def get_connection(self, key: str) -> Any:
        """Bağlantı al"""
        current_time = time.time()
        
        # Eski bağlantıları temizle
        self._cleanup_old_connections(current_time)
        
        if key in self.pool:
            self.last_used[key] = current_time
            return self.pool[key]
        
        return None

    def add_connection(self, key: str, connection: Any) -> None:
        """Bağlantı ekle"""
        if len(self.pool) >= self.max_size:
            self._remove_oldest_connection()
        
        self.pool[key] = connection
        self.last_used[key] = time.time()

    def _cleanup_old_connections(self, current_time: float) -> None:
        """Eski bağlantıları temizle"""
        keys_to_remove = [
            key for key, last_used in self.last_used.items()
            if current_time - last_used > self.timeout
        ]
        
        for key in keys_to_remove:
            self._close_connection(key)
            del self.pool[key]
            del self.last_used[key]

    def _remove_oldest_connection(self) -> None:
        """En eski bağlantıyı kaldır"""
        if not self.last_used:
            return
        
        oldest_key = min(self.last_used.items(), key=lambda x: x[1])[0]
        self._close_connection(oldest_key)
        del self.pool[oldest_key]
        del self.last_used[oldest_key]

    def _close_connection(self, key: str) -> None:
        """Bağlantıyı kapat"""
        try:
            if hasattr(self.pool[key], 'close'):
                self.pool[key].close()
        except Exception as e:
            logger.log_error(e, {"connection": "close_failed"})

    def cleanup(self) -> None:
        """Tüm bağlantıları temizle"""
        for key in list(self.pool.keys()):
            self._close_connection(key)
            del self.pool[key]
            del self.last_used[key]

    def close(self) -> None:
        """Havuzu kapat"""
        self.cleanup()

# Kaynak yöneticisini başlat
resource_manager = ResourceManager()

# Mantıksal İyileştirmeler Sınıfları
class RiskManager:
    """Risk yönetimi"""
    def __init__(self):
        self.max_daily_loss = Decimal(str(settings.MAX_DAILY_LOSS))
        self.max_position_size = Decimal(str(settings.MAX_POSITION_SIZE))
        self.stop_loss_multiplier = Decimal(str(settings.STOP_LOSS_MULTIPLIER))
        self.take_profit_multiplier = Decimal(str(settings.TAKE_PROFIT_MULTIPLIER))
        self.daily_loss = Decimal('0')
        self.last_reset = datetime.utcnow().date()
        self.position_sizes = {}
        self.risk_scores = {}

    def calculate_position_size(self, symbol: str, current_price: Decimal, 
                              risk_score: float) -> Decimal:
        """Pozisyon boyutunu hesapla"""
        try:
            # Risk skoruna göre pozisyon boyutunu ayarla
            risk_adjusted_size = self.max_position_size * Decimal(str(risk_score))
            
            # Günlük kayıp limitini kontrol et
            available_risk = self.max_daily_loss - self.daily_loss
            if available_risk <= 0:
                return Decimal('0')
            
            # Kullanılabilir risk ve ayarlanmış pozisyon boyutunu karşılaştır
            position_size = min(risk_adjusted_size, available_risk)
            
            # Fiyat bazında miktarı hesapla
            quantity = position_size / current_price
            
            self.position_sizes[symbol] = quantity
            return quantity
            
        except Exception as e:
            logger.log_error(e, {"risk": "position_size_calculation"})
            return Decimal('0')

    def update_daily_loss(self, pnl: Decimal) -> None:
        """Günlük kaybı güncelle"""
        current_date = datetime.utcnow().date()
        if current_date != self.last_reset:
            self.daily_loss = Decimal('0')
            self.last_reset = current_date
        
        if pnl < 0:
            self.daily_loss += abs(pnl)

    def calculate_risk_score(self, symbol: str, market_data: Dict) -> float:
        """Risk skorunu hesapla"""
        try:
            # Teknik göstergeler
            volatility = self._calculate_volatility(market_data['prices'])
            trend_strength = self._calculate_trend_strength(market_data['prices'])
            volume_ratio = self._calculate_volume_ratio(market_data['volumes'])
            
            # Piyasa durumu
            market_condition = self._analyze_market_condition(market_data)
            
            # Risk faktörlerini birleştir
            risk_score = (
                volatility * 0.3 +
                (1 - trend_strength) * 0.2 +
                volume_ratio * 0.2 +
                market_condition * 0.3
            )
            
            # Risk skorunu normalize et
            risk_score = max(0.1, min(1.0, risk_score))
            
            self.risk_scores[symbol] = risk_score
            return risk_score
            
        except Exception as e:
            logger.log_error(e, {"risk": "score_calculation"})
            return 0.5  # Varsayılan orta risk

    def _calculate_volatility(self, prices: List[Decimal]) -> float:
        """Volatilite hesapla"""
        returns = np.diff([float(p) for p in prices])
        return float(np.std(returns))

    def _calculate_trend_strength(self, prices: List[Decimal]) -> float:
        """Trend gücünü hesapla"""
        prices_array = np.array([float(p) for p in prices])
        slope, _, r_value, _, _ = stats.linregress(range(len(prices_array)), prices_array)
        return abs(r_value)

    def _calculate_volume_ratio(self, volumes: List[Decimal]) -> float:
        """Hacim oranını hesapla"""
        if len(volumes) < 2:
            return 0.5
        current_volume = float(volumes[-1])
        avg_volume = float(sum(volumes[:-1])) / (len(volumes) - 1)
        return min(1.0, current_volume / avg_volume)

    def _analyze_market_condition(self, market_data: Dict) -> float:
        """Piyasa durumunu analiz et"""
        try:
            # Teknik göstergeler
            rsi = market_data.get('rsi', 50)
            macd = market_data.get('macd', 0)
            macd_signal = market_data.get('macd_signal', 0)
            
            # Gösterge skorlarını hesapla
            rsi_score = 1 - abs(rsi - 50) / 50
            macd_score = 1 if (macd > macd_signal) else 0
            
            # Piyasa durumu skorunu hesapla
            market_score = (rsi_score + macd_score) / 2
            return float(market_score)
            
        except Exception as e:
            logger.log_error(e, {"risk": "market_analysis"})
            return 0.5

class DecisionManager:
    """Karar yönetimi"""
    def __init__(self):
        self.strategy = Strategy()
        self.risk_manager = RiskManager()
        self.model = self._train_model()
        self.scaler = StandardScaler()
        self.decision_history = []
        self.max_history_size = 1000

    def _train_model(self) -> RandomForestClassifier:
        """Karar modelini eğit"""
        try:
            # Örnek veri seti oluştur (gerçek uygulamada geçmiş veriler kullanılmalı)
            X = np.random.rand(100, 5)  # 5 özellik
            y = np.random.randint(0, 2, 100)  # 0: sat, 1: al
            
            # Modeli eğit
            model = RandomForestClassifier(n_estimators=100)
            model.fit(X, y)
            return model
            
        except Exception as e:
            logger.log_error(e, {"decision": "model_training"})
            return None

    def make_decision(self, symbol: str, market_data: Dict, 
                     current_balance: Decimal) -> Optional[Dict]:
        """İşlem kararı al"""
        try:
            # Risk skorunu hesapla
            risk_score = self.risk_manager.calculate_risk_score(symbol, market_data)
            
            # Piyasa verilerini hazırla
            features = self._prepare_features(market_data)
            
            # Model tahminini al
            if self.model:
                prediction = self.model.predict_proba([features])[0]
                model_confidence = float(prediction[1])  # Alım olasılığı
            else:
                model_confidence = 0.5
            
            # Strateji kararını al
            strategy_decision = self.strategy.decide_trade(
                current_balance,
                market_data.get('current_pnl', Decimal('0')),
                market_data
            )
            
            # Kararları birleştir
            final_decision = self._combine_decisions(
                model_confidence,
                strategy_decision,
                risk_score
            )
            
            # Kararı kaydet
            self._save_decision(symbol, final_decision, market_data)
            
            return final_decision
            
        except Exception as e:
            logger.log_error(e, {"decision": "making"})
            return None

    def _prepare_features(self, market_data: Dict) -> np.ndarray:
        """Özellikleri hazırla"""
        try:
            features = [
                float(market_data.get('rsi', 50)) / 100,
                float(market_data.get('macd', 0)),
                float(market_data.get('macd_signal', 0)),
                float(market_data.get('volatility', 0.5)),
                float(market_data.get('volume_ratio', 0.5))
            ]
            return np.array(features)
        except Exception as e:
            logger.log_error(e, {"decision": "feature_preparation"})
            return np.zeros(5)

    def _combine_decisions(self, model_confidence: float, 
                         strategy_decision: Dict, 
                         risk_score: float) -> Dict:
        """Kararları birleştir"""
        try:
            # Strateji kararını ağırlıklandır
            strategy_weight = 0.6
            model_weight = 0.4
            
            # Risk skorunu dikkate al
            risk_adjusted_confidence = model_confidence * risk_score
            
            # Nihai kararı hesapla
            final_confidence = (
                strategy_weight * float(strategy_decision.get('confidence', 0.5)) +
                model_weight * risk_adjusted_confidence
            )
            
            # Karar eşiğini kontrol et
            action = 'buy' if final_confidence > 0.6 else 'sell' if final_confidence < 0.4 else 'hold'
            
            return {
                'action': action,
                'confidence': final_confidence,
                'risk_score': risk_score,
                'model_confidence': model_confidence,
                'strategy_confidence': strategy_decision.get('confidence', 0.5)
            }
            
        except Exception as e:
            logger.log_error(e, {"decision": "combining"})
            return {'action': 'hold', 'confidence': 0.5}

    def _save_decision(self, symbol: str, decision: Dict, 
                      market_data: Dict) -> None:
        """Kararı kaydet"""
        try:
            decision_record = {
                'timestamp': datetime.utcnow().isoformat(),
                'symbol': symbol,
                'decision': decision,
                'market_data': market_data
            }
            
            self.decision_history.append(decision_record)
            if len(self.decision_history) > self.max_history_size:
                self.decision_history.pop(0)
                
        except Exception as e:
            logger.log_error(e, {"decision": "saving"})

class PerformanceOptimizer:
    """Performans optimizasyonu"""
    def __init__(self):
        self.cycle_times = []
        self.memory_usage = []
        self.api_calls = []
        self.optimization_interval = 3600  # 1 saat
        self.last_optimization = time.time()

    def record_cycle_time(self, cycle_time: float) -> None:
        """Döngü süresini kaydet"""
        self.cycle_times.append(cycle_time)
        if len(self.cycle_times) > 100:
            self.cycle_times.pop(0)

    def record_memory_usage(self) -> None:
        """Bellek kullanımını kaydet"""
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss)
        if len(self.memory_usage) > 100:
            self.memory_usage.pop(0)

    def record_api_call(self, duration: float) -> None:
        """API çağrısını kaydet"""
        self.api_calls.append(duration)
        if len(self.api_calls) > 100:
            self.api_calls.pop(0)

    def optimize_performance(self) -> None:
        """Performansı optimize et"""
        try:
            current_time = time.time()
            if current_time - self.last_optimization < self.optimization_interval:
                return

            # Döngü sürelerini analiz et
            if self.cycle_times:
                avg_cycle_time = sum(self.cycle_times) / len(self.cycle_times)
                if avg_cycle_time > settings.CYCLE_INTERVAL * 0.8:
                    self._optimize_cycle_time()

            # Bellek kullanımını analiz et
            if self.memory_usage:
                avg_memory = sum(self.memory_usage) / len(self.memory_usage)
                if avg_memory > 500 * 1024 * 1024:  # 500MB
                    self._optimize_memory_usage()

            # API çağrılarını analiz et
            if self.api_calls:
                avg_api_time = sum(self.api_calls) / len(self.api_calls)
                if avg_api_time > 1.0:  # 1 saniye
                    self._optimize_api_calls()

            self.last_optimization = current_time
            logger.logger.info("Performans optimizasyonu tamamlandı")

        except Exception as e:
            logger.log_error(e, {"performance": "optimization"})

    def _optimize_cycle_time(self) -> None:
        """Döngü süresini optimize et"""
        try:
            # Önbellek boyutunu ayarla
            cache_manager.ohlcv_cache.clear()
            cache_manager.indicators_cache.clear()
            
            # Asenkron işlemleri optimize et
            async_manager.executor._max_workers = min(
                5, 
                max(2, len(settings.SYMBOLS) // 2)
            )
            
        except Exception as e:
            logger.log_error(e, {"performance": "cycle_optimization"})

    def _optimize_memory_usage(self) -> None:
        """Bellek kullanımını optimize et"""
        try:
            # Garbage collection'u tetikle
            gc.collect()
            
            # Önbellekleri temizle
            cache_manager.clear_all()
            
            # Eski kararları temizle
            if decision_manager.decision_history:
                decision_manager.decision_history = decision_manager.decision_history[-500:]
                
        except Exception as e:
            logger.log_error(e, {"performance": "memory_optimization"})

    def _optimize_api_calls(self) -> None:
        """API çağrılarını optimize et"""
        try:
            # API isteklerini birleştir
            api_client.merge_requests = True
            
            # Yeniden deneme stratejisini güncelle
            api_client.retry_strategy.max_retries = min(
                5, 
                api_client.retry_strategy.max_retries + 1
            )
            
        except Exception as e:
            logger.log_error(e, {"performance": "api_optimization"})

# Mantıksal yöneticileri başlat
risk_manager = RiskManager()
decision_manager = DecisionManager()
performance_optimizer = PerformanceOptimizer()

# Mevcut kodun devamı...
def run_bot_cycle(symbol: str) -> Optional[TradeResult]:
    """
    Bot döngüsünü çalıştır
    """
    global start_balance
    cycle_start = time.time()

    try:
        # Kaynak kullanımını kontrol et
        resource_manager.check_resources()

        # Konfigürasyon kontrollerini yap
        config_manager.reload_config('settings')
        config_manager.reload_config('strategy')
        config_manager.reload_config('security')

        # Güvenlik kontrollerini yap
        security_manager.check_security_measures()

        # Debug log
        logger.log_debug(f"Döngü başlatılıyor: {symbol}")

        # --- Açık pozisyon kontrolü ---
        base_asset = symbol.replace("USDT", "")
        current_position = executor.get_balance(base_asset)
        if current_position > Decimal('0'):
            logger.logger.info(f"[EXECUTOR] {symbol} pozisyonu zaten açık, atlanıyor.")
            return None

        # İnsanvari gecikme
        time.sleep(random.uniform(2, 10))
        logger.logger.info(f"[CYCLE] {symbol} için döngü başlıyor.")

        # Stealth kontrolü
        stealth.maybe_enter_sleep()

        # Zaman stratejisi
        current_mode = get_current_strategy_mode()
        logger.log_debug("Zaman stratejisi", {"mode": current_mode})

        # Küresel risk analizi
        risk_level = GlobalRiskAnalyzer().evaluate_risk_level()
        logger.log_debug("Risk analizi", {"level": risk_level})

        # Asenkron veri toplama
        loop = asyncio.get_event_loop()
        ohlcv_15m = loop.run_until_complete(fetch_ohlcv_async(symbol, "15m"))
        ohlcv_1h = loop.run_until_complete(fetch_ohlcv_async(symbol, "1h"))

        validate_ohlcv_data(ohlcv_15m, "15m")
        validate_ohlcv_data(ohlcv_1h, "1h")

        prices_15m = [Decimal(str(c[4])) for c in ohlcv_15m]
        prices_1h = [Decimal(str(c[4])) for c in ohlcv_1h]

        # Asenkron gösterge hesaplama
        rsi_15m, macd_15m, macd_signal_15m = loop.run_until_complete(calculate_indicators_async(prices_15m))
        rsi_1h, macd_1h, macd_signal_1h = loop.run_until_complete(calculate_indicators_async(prices_1h))

        # Piyasa verilerini hazırla
        market_data = {
            'prices': prices_15m,
            'volumes': [Decimal(str(c[5])) for c in ohlcv_15m],
            'rsi': rsi_15m,
            'macd': macd_15m[-1] if macd_15m else None,
            'macd_signal': macd_signal_15m[-1] if macd_signal_15m else None,
            'volatility': risk_manager._calculate_volatility(prices_15m),
            'volume_ratio': risk_manager._calculate_volume_ratio([Decimal(str(c[5])) for c in ohlcv_15m]),
            'current_pnl': Decimal('0')  # Başlangıçta 0
        }

        # Bakiye ve PnL hesaplama
        try:
            current_balance = Decimal(str(executor.get_balance('USDT')))
            current_pnl = current_balance - start_balance
            market_data['current_pnl'] = current_pnl
            logger.log_debug("Bakiye bilgisi", {
                "current_balance": current_balance,
                "current_pnl": current_pnl
            })
        except Exception as e:
            error_tracker.track_error("balance_error")
            raise APIError(f"Bakiye bilgisi alınamadı: {e}")

        # Karar alma
        decision = decision_manager.make_decision(symbol, market_data, current_balance)
        if not decision or decision['action'] == 'hold':
            logger.logger.info(f"[DECISION] {symbol} için işlem yapılmadı.")
            return None

        # Risk yönetimi
        risk_score = risk_manager.calculate_risk_score(symbol, market_data)
        position_size = risk_manager.calculate_position_size(
            symbol,
            prices_15m[-1],
            risk_score
        )

        if position_size <= 0:
            logger.logger.warning(f"[RISK] {symbol} için pozisyon boyutu 0.")
            return None

        # İşlem yürütme
        trade_result = executor.manage_position(
            symbol,
            decision['action'],
            position_size
        )

        if not trade_result:
            error_tracker.track_error("trade_execution_error")
            raise APIError("İşlem yürütülemedi")

        # Performans metriklerini kaydet
        cycle_duration = time.time() - cycle_start
        performance_optimizer.record_cycle_time(cycle_duration)
        performance_optimizer.record_memory_usage()
        performance_optimizer.optimize_performance()

        result = TradeResult.from_dict({
            'symbol': symbol,
            'action': trade_result.get('action'),
            'quantity': trade_result.get('quantity'),
            'price': trade_result.get('price'),
            'pnl': trade_result.get('pnl'),
            'timestamp': datetime.utcnow(),
            'duration': cycle_duration
        })

        # İşlem logunu kaydet
        logger.log_trade({
            'symbol': symbol,
            'action': result.action,
            'quantity': str(result.quantity),
            'price': str(result.price),
            'pnl': str(result.pnl),
            'duration': result.duration,
            'timestamp': result.timestamp.isoformat(),
            'risk_score': risk_score,
            'decision_confidence': decision['confidence']
        })

        return result

    except TradingBotError as e:
        error_tracker.track_error(type(e).__name__)
        logger.log_error(e, {'symbol': symbol, 'cycle_start': cycle_start})
        return None
    except Exception as e:
        error_tracker.track_error('unexpected_error')
        logger.log_error(e, {'symbol': symbol, 'cycle_start': cycle_start})
        return None

def print_metrics():
    global peak_balance, max_drawdown
    curr_balance = executor.get_balance('USDT')
    peak_balance = max(peak_balance, curr_balance)
    drawdown     = peak_balance - curr_balance
    max_drawdown = max(max_drawdown, drawdown)
    pnl_pct      = ((curr_balance - start_balance) / start_balance * 100) if start_balance else 0
    progress_pct = (curr_balance / settings.TARGET_USDT * 100)
    avg_dur      = (sum(trade_durations) / len(trade_durations)) if trade_durations else 0
    win_rate     = (win_trades / total_trades * 100) if total_trades else 0

    print(f"Anlık Sermaye:       {curr_balance:.2f} USDT")
    print(f"Toplam PnL:          {(curr_balance - start_balance):.2f} USDT ({pnl_pct:+.2f}%)")
    print(f"Hedefe Progress:     {progress_pct:.4f}%")
    print(f"Toplam İşlem:        {total_trades}  Kazanan: {win_trades}  ({win_rate:.1f}%)")
    print(f"Max Drawdown:        {max_drawdown:.2f} USDT")
    print(f"Ortalama Trade Süre: {avg_dur:.1f}s")

# API istemcisini başlat
api_config = APIConfig()
api_config.validate_credentials()
api_client = APIClient(api_config)

def fetch_ohlcv_from_binance(symbol: str, interval: str, limit: int = 50) -> List[List[Union[int, float]]]:
    """OHLCV verilerini güvenli şekilde al"""
    try:
        endpoint = '/api/v3/klines'
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        response = api_client.make_request('GET', endpoint, params=params)
        return [[
            int(candle[0]),  # timestamp
            float(candle[1]),  # open
            float(candle[2]),  # high
            float(candle[3]),  # low
            float(candle[4]),  # close
            float(candle[5])   # volume
        ] for candle in response]
        
    except Exception as e:
        logger.logger.error(f"OHLCV verisi alınamadı ({symbol}, {interval}): {str(e)}")
        raise APIError(f"OHLCV verisi alınamadı: {str(e)}")

# Zamanlama Mekanizmaları Sınıfları
class TimeManager:
    """Zamanlama yönetimi"""
    def __init__(self):
        self.ntp_client = ntplib.NTPClient()
        self.time_offset = 0
        self.last_sync = 0
        self.sync_interval = 3600  # 1 saat
        self.tasks = PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.stop_event = Event()
        self.scheduler_thread = None
        self._setup_scheduler()

    def _setup_scheduler(self) -> None:
        """Zamanlayıcıyı kur"""
        self.scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def _run_scheduler(self) -> None:
        """Zamanlayıcı döngüsü"""
        while not self.stop_event.is_set():
            try:
                self._process_tasks()
                time.sleep(1)
            except Exception as e:
                logger.log_error(e, {"scheduler": "error"})

    def _process_tasks(self) -> None:
        """Görevleri işle"""
        current_time = self.get_current_time()
        
        while not self.tasks.empty():
            task = self.tasks.get()
            if task.execution_time <= current_time:
                self.executor.submit(self._execute_task, task)
            else:
                self.tasks.put(task)
                break

    def _execute_task(self, task: 'ScheduledTask') -> None:
        """Görevi çalıştır"""
        try:
            task.function(*task.args, **task.kwargs)
        except Exception as e:
            logger.log_error(e, {"task": task.name})

    def sync_time(self) -> None:
        """NTP sunucusu ile zamanı senkronize et"""
        try:
            response = self.ntp_client.request('pool.ntp.org')
            self.time_offset = response.offset
            self.last_sync = time.time()
            logger.logger.info(f"Zaman senkronizasyonu tamamlandı. Offset: {self.time_offset:.3f}s")
        except Exception as e:
            logger.log_error(e, {"time_sync": "failed"})

    def get_current_time(self) -> float:
        """Senkronize edilmiş zamanı al"""
        if time.time() - self.last_sync > self.sync_interval:
            self.sync_time()
        return time.time() + self.time_offset

    def schedule_task(self, name: str, function: callable, delay: float, 
                     *args, **kwargs) -> None:
        """Görev zamanla"""
        execution_time = self.get_current_time() + delay
        task = ScheduledTask(name, function, execution_time, args, kwargs)
        self.tasks.put(task)
        logger.logger.debug(f"Görev zamanlandı: {name}")

    def cleanup(self) -> None:
        """Kaynakları temizle"""
        self.stop_event.set()
        if self.scheduler_thread:
            self.scheduler_thread.join()
        self.executor.shutdown(wait=True)

@dataclass
class ScheduledTask:
    """Zamanlanmış görev"""
    name: str
    function: callable
    execution_time: float
    args: tuple
    kwargs: dict

    def __lt__(self, other):
        return self.execution_time < other.execution_time

class CycleManager:
    """Döngü yönetimi"""
    def __init__(self):
        self.time_manager = TimeManager()
        self.cycle_interval = settings.CYCLE_INTERVAL
        self.jitter_min = settings.CYCLE_JITTER_MIN
        self.jitter_max = settings.CYCLE_JITTER_MAX
        self.last_cycle = {}
        self.cycle_locks = {}
        self._setup_cycles()

    def _setup_cycles(self) -> None:
        """Döngüleri kur"""
        # Ana döngü
        self.time_manager.schedule_task(
            'main_cycle',
            self._run_main_cycle,
            self.cycle_interval
        )

        # İkincil döngüler
        self.time_manager.schedule_task(
            'cleanup_cycle',
            self._run_cleanup_cycle,
            300  # 5 dakika
        )

        self.time_manager.schedule_task(
            'monitoring_cycle',
            self._run_monitoring_cycle,
            60  # 1 dakika
        )

    def _run_main_cycle(self) -> None:
        """Ana döngüyü çalıştır"""
        try:
            # Döngü başında dönem bilgilerini yeniden logla
            _ = update_settings_for_period()

            # Altcoin seçim
            if settings.USE_DYNAMIC_SYMBOL_SELECTION:
                symbols_to_trade = select_coins() or settings.SYMBOLS
            else:
                symbols_to_trade = settings.SYMBOLS

            for symbol in symbols_to_trade:
                if self._can_run_cycle(symbol):
                    self._execute_cycle(symbol)

            # Sonraki döngüyü zamanla
            next_interval = self.cycle_interval + random.uniform(
                self.jitter_min,
                self.jitter_max
            )
            self.time_manager.schedule_task(
                'main_cycle',
                self._run_main_cycle,
                next_interval
            )

        except Exception as e:
            logger.log_error(e, {"cycle": "main"})
            # Hata durumunda kısa süre sonra tekrar dene
            self.time_manager.schedule_task(
                'main_cycle',
                self._run_main_cycle,
                60  # 1 dakika
            )

    def _run_cleanup_cycle(self) -> None:
        """Temizlik döngüsünü çalıştır"""
        try:
            resource_manager.cleanup()
            self.time_manager.schedule_task(
                'cleanup_cycle',
                self._run_cleanup_cycle,
                300  # 5 dakika
            )
        except Exception as e:
            logger.log_error(e, {"cycle": "cleanup"})

    def _run_monitoring_cycle(self) -> None:
        """İzleme döngüsünü çalıştır"""
        try:
            performance_monitor.log_metrics()
            self.time_manager.schedule_task(
                'monitoring_cycle',
                self._run_monitoring_cycle,
                60  # 1 dakika
            )
        except Exception as e:
            logger.log_error(e, {"cycle": "monitoring"})

    def _can_run_cycle(self, symbol: str) -> bool:
        """Döngünün çalıştırılıp çalıştırılamayacağını kontrol et"""
        current_time = self.time_manager.get_current_time()
        last_cycle_time = self.last_cycle.get(symbol, 0)
        
        if current_time - last_cycle_time < self.cycle_interval:
            return False
        
        if symbol not in self.cycle_locks:
            self.cycle_locks[symbol] = Lock()
        
        return not self.cycle_locks[symbol].locked()

    def _execute_cycle(self, symbol: str) -> None:
        """Döngüyü çalıştır"""
        lock = self.cycle_locks[symbol]
        if lock.acquire(blocking=False):
            try:
                result = run_bot_cycle(symbol)
                if result:
                    self._handle_cycle_result(result)
            finally:
                lock.release()
                self.last_cycle[symbol] = self.time_manager.get_current_time()

    def _handle_cycle_result(self, result: TradeResult) -> None:
        """Döngü sonucunu işle"""
        global total_trades, win_trades, loss_trades, trade_durations
        
        total_trades += 1
        if result.pnl >= 0:
            win_trades += 1
        else:
            loss_trades += 1
        trade_durations.append(result.duration)

        print(f"{result.timestamp} - {result.symbol} "
              f"{result.action} {result.quantity} @ {result.price} → "
              f"PnL: {result.pnl:+.2f} USDT")

        if settings.NOTIFIER_ENABLED:
            msg = (f"İşlem: {result.action} {result.symbol} "
                   f"@ {result.price:.2f} USD, PnL: {result.pnl:+.2f} USDT")
            send_notification(msg)

        log_trade_csv(result)
        print_metrics()

    def cleanup(self) -> None:
        """Kaynakları temizle"""
        self.time_manager.cleanup()

# Zamanlama yöneticisini başlat
time_manager = TimeManager()
cycle_manager = CycleManager()

if __name__ == "__main__":
    try:
        # → Performans optimizasyonu ve parametre kontrolü
        optimize_strategy_parameters()

        # Ana döngüyü başlat
        cycle_manager._run_main_cycle()

        # Ana döngüyü bekle
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.logger.info("Bot durduruluyor...")
    finally:
        # Kaynakları temizle
        cycle_manager.cleanup()
        resource_manager.cleanup()
        config_manager.cleanup()
        logger.logger.info("Bot durduruldu.")

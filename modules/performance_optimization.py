import time
import psutil
import threading
import gc
import os
import json
from datetime import datetime
from core.logger import BotLogger

logger = BotLogger()

class PerformanceOptimizer:
    def __init__(self):
        self.monitoring_interval = 300  # 5 dakika
        self.monitoring_thread = None
        self.is_monitoring = False
        self.performance_data = []
        self.max_memory_usage = 80  # %80
        self.max_cpu_usage = 70  # %70
        self.optimization_threshold = 0.8  # %80
        
    def start_monitoring(self):
        """Performans izlemeyi başlatır"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitor_performance)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            logger.log("[PERF] Performans izleme başlatıldı")
            
    def stop_monitoring(self):
        """Performans izlemeyi durdurur"""
        self.is_monitoring = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
            logger.log("[PERF] Performans izleme durduruldu")
            
    def _monitor_performance(self):
        """Performans metriklerini izler"""
        while self.is_monitoring:
            try:
                # CPU kullanımı
                cpu_percent = psutil.cpu_percent(interval=1)
                
                # Bellek kullanımı
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                
                # Disk kullanımı
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                
                # Ağ kullanımı
                net_io = psutil.net_io_counters()
                net_bytes_sent = net_io.bytes_sent
                net_bytes_recv = net_io.bytes_recv
                
                # Performans verilerini kaydet
                performance_data = {
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_percent": disk_percent,
                    "net_bytes_sent": net_bytes_sent,
                    "net_bytes_recv": net_bytes_recv
                }
                
                self.performance_data.append(performance_data)
                
                # Son 100 veriyi tut
                if len(self.performance_data) > 100:
                    self.performance_data = self.performance_data[-100:]
                
                # Performans sorunlarını kontrol et
                if cpu_percent > self.max_cpu_usage or memory_percent > self.max_memory_usage:
                    logger.log(f"[PERF] Yüksek kaynak kullanımı: CPU={cpu_percent}%, MEM={memory_percent}%")
                    self.optimize_performance()
                
                # Performans verilerini kaydet
                self._save_performance_data()
                
                # Belirli aralıklarla bekle
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.log(f"[PERF] İzleme hatası: {e}")
                time.sleep(60)  # Hata durumunda 1 dakika bekle
                
    def _save_performance_data(self):
        """Performans verilerini dosyaya kaydeder"""
        try:
            os.makedirs("data", exist_ok=True)
            filename = f"data/performance_{datetime.now().strftime('%Y%m%d')}.json"
            
            with open(filename, "w") as f:
                json.dump(self.performance_data, f, indent=2)
        except Exception as e:
            logger.log(f"[PERF] Veri kaydetme hatası: {e}")
            
    def optimize_performance(self):
        """Performans optimizasyonu yapar"""
        try:
            # Bellek optimizasyonu
            if psutil.virtual_memory().percent > self.max_memory_usage:
                logger.log("[PERF] Bellek optimizasyonu yapılıyor")
                gc.collect()  # Çöp toplama
                
            # CPU optimizasyonu
            if psutil.cpu_percent() > self.max_cpu_usage:
                logger.log("[PERF] CPU optimizasyonu yapılıyor")
                # Yüksek CPU kullanan işlemleri tespit et
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    try:
                        if proc.info['cpu_percent'] > 10:  # %10'dan fazla CPU kullanan işlemler
                            logger.log(f"[PERF] Yüksek CPU kullanan işlem: {proc.info['name']} ({proc.info['pid']})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
            # Disk optimizasyonu
            if psutil.disk_usage('/').percent > 90:
                logger.log("[PERF] Disk optimizasyonu yapılıyor")
                # Eski log dosyalarını temizle
                self._cleanup_old_logs()
                
            logger.log("[PERF] Performans optimizasyonu tamamlandı")
            
        except Exception as e:
            logger.log(f"[PERF] Optimizasyon hatası: {e}")
            
    def _cleanup_old_logs(self):
        """Eski log dosyalarını temizler"""
        try:
            log_dir = "logs"
            if os.path.exists(log_dir):
                current_time = time.time()
                for filename in os.listdir(log_dir):
                    filepath = os.path.join(log_dir, filename)
                    # 7 günden eski dosyaları sil
                    if os.path.getmtime(filepath) < current_time - 7 * 86400:
                        os.remove(filepath)
                        logger.log(f"[PERF] Eski log dosyası silindi: {filename}")
        except Exception as e:
            logger.log(f"[PERF] Log temizleme hatası: {e}")
            
    def get_performance_metrics(self):
        """Performans metriklerini döndürür"""
        if not self.performance_data:
            return {}
            
        latest = self.performance_data[-1]
        
        # Ortalama değerleri hesapla
        avg_cpu = sum(d["cpu_percent"] for d in self.performance_data) / len(self.performance_data)
        avg_memory = sum(d["memory_percent"] for d in self.performance_data) / len(self.performance_data)
        
        return {
            "current": latest,
            "average": {
                "cpu_percent": avg_cpu,
                "memory_percent": avg_memory
            },
            "history_count": len(self.performance_data)
        }
        
    def optimize_performance_infrastructure(self):
        """Performans altyapısını optimize eder"""
        # İzlemeyi başlat
        self.start_monitoring()
        
        # Mevcut performans durumunu kontrol et
        metrics = self.get_performance_metrics()
        if metrics:
            logger.log(f"[PERF] Mevcut performans: CPU={metrics['current']['cpu_percent']}%, MEM={metrics['current']['memory_percent']}%")
            
        # Gerekirse optimizasyon yap
        if metrics and (metrics['current']['cpu_percent'] > self.max_cpu_usage or 
                        metrics['current']['memory_percent'] > self.max_memory_usage):
            self.optimize_performance()
            
        return metrics

# Global instance
performance_optimizer = PerformanceOptimizer()

def optimize_performance_infrastructure():
    """Dışa açık fonksiyon"""
    return performance_optimizer.optimize_performance_infrastructure() 
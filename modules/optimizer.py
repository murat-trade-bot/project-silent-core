# optimizer.py
"""
Gelişmiş Otomatik Parametre Optimizasyonu Modülü
"""
import json
import os as _os
import datetime
from typing import Dict, Any, List, Optional
from statistics import mean, pstdev

PARAM_FILE = 'config/optimizer_params.json'
PERF_LOG_FILE = 'logs/performance_log.json'
CHANGE_LOG_FILE = 'logs/optimizer_changes.json'

class Optimizer:
    def __init__(self, 
                 param_file: str = PARAM_FILE, 
                 perf_log_file: str = PERF_LOG_FILE,
                 change_log_file: str = CHANGE_LOG_FILE):
        self.param_file = param_file
        self.perf_log_file = perf_log_file
        self.change_log_file = change_log_file
        self.params = self._load_params()
        self.performance = self._load_performance()

    def _safe_load_json(self, file_path: str, default):
        """Dosya okunamazsa varsayılan değeri döndür."""
        try:
            if _os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _load_params(self) -> Dict[str, Any]:
        return self._safe_load_json(self.param_file, {
            'tp_pct': 0.4,
            'sl_pct': 0.2,
            'signal_threshold': 0.7,
            'volume_filter': 0.5,
            'mode': 'balanced'  # conservative / aggressive / balanced
        })

    def _save_params(self):
        dirpath = _os.path.dirname(self.param_file)
        if dirpath:
            _os.makedirs(dirpath, exist_ok=True)
        with open(self.param_file, 'w') as f:
            json.dump(self.params, f, indent=2)

    def _load_performance(self) -> List[Dict[str, Any]]:
        return self._safe_load_json(self.perf_log_file, [])

    def _save_performance(self):
        dirpath = _os.path.dirname(self.perf_log_file)
        if dirpath:
            _os.makedirs(dirpath, exist_ok=True)
        with open(self.perf_log_file, 'w') as f:
            json.dump(self.performance, f, indent=2)

    def _log_change(self, reason: str, old_params: Dict[str, Any], new_params: Dict[str, Any]):
        """Parametre değişiklik geçmişini loglar."""
        changes = self._safe_load_json(self.change_log_file, [])
        changes.append({
            'date': datetime.datetime.now().isoformat(),
            'reason': reason,
            'old_params': old_params,
            'new_params': new_params
        })
        dirpath = _os.path.dirname(self.change_log_file)
        if dirpath:
            _os.makedirs(dirpath, exist_ok=True)
        with open(self.change_log_file, 'w') as f:
            json.dump(changes, f, indent=2)

    def log_performance(self, date: str, profit_pct: float, win_rate: float, max_drawdown: float, trades: int):
        self.performance.append({
            'date': date,
            'profit_pct': profit_pct,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trades': trades
        })
        self._save_performance()

    def optimize_params(self, period: str = 'week', notify_func: Optional[callable] = None):
        """Performansa göre parametreleri optimize eder."""
        now = datetime.date.today()
        start = now - datetime.timedelta(days=7 if period == 'week' else 30)

        perf = [p for p in self.performance if p['date'] >= start.isoformat()]
        if not perf:
            return self.params

        avg_profit = mean(p['profit_pct'] for p in perf)
        avg_win = mean(p['win_rate'] for p in perf)
        avg_dd = mean(p['max_drawdown'] for p in perf)

        std_profit = pstdev(p['profit_pct'] for p in perf) or 1

        old_params = self.params.copy()

        # Mode etkisi
        mode_factor = 1.0
        if self.params.get('mode') == 'conservative':
            mode_factor = 0.8
        elif self.params.get('mode') == 'aggressive':
            mode_factor = 1.2

        # Kar düşükse
        if avg_profit < 0:
            self.params['tp_pct'] = max(0.1, self.params['tp_pct'] - 0.05 * abs(avg_profit / std_profit) * mode_factor)
            self.params['sl_pct'] = min(0.6, self.params['sl_pct'] + 0.05 * mode_factor)
        # Kar yüksekse
        elif avg_profit > 2:
            self.params['tp_pct'] = min(1.5, self.params['tp_pct'] + 0.05 * (avg_profit / std_profit) * mode_factor)
            self.params['sl_pct'] = max(0.05, self.params['sl_pct'] - 0.05 * mode_factor)

        # Win rate düşükse
        if avg_win < 0.5:
            self.params['signal_threshold'] = min(0.95, self.params['signal_threshold'] + 0.05 * mode_factor)

        # Drawdown yüksekse
        if avg_dd > 5:
            self.params['volume_filter'] = min(1.0, self.params['volume_filter'] + 0.1 * mode_factor)

        self._save_params()
        self._log_change(reason=f"Optimization for {period}", old_params=old_params, new_params=self.params)

        # Bildirim
        if notify_func:
            try:
                notify_func(f"[Optimizer] {period} optimizasyonu yapıldı. Yeni parametreler: {self.params}")
            except Exception:
                pass

        return self.params

    def get_params(self) -> Dict[str, Any]:
        return self.params

# Test fonksiyonu
def test_optimizer():
    import tempfile
    tmp_param = tempfile.mktemp()
    tmp_perf = tempfile.mktemp()
    tmp_changes = tempfile.mktemp()

    opt = Optimizer(param_file=tmp_param, perf_log_file=tmp_perf, change_log_file=tmp_changes)
    
    for i in range(7):
        opt.log_performance(
            date=(datetime.date.today() - datetime.timedelta(days=i)).isoformat(),
            profit_pct=1.5 - i*0.5,
            win_rate=0.6 - i*0.05,
            max_drawdown=3 + i,
            trades=5 + i
        )
    
    print('Eski parametreler:', opt.get_params())
    new_params = opt.optimize_params('week')
    print('Optimize parametreler:', new_params)

if __name__ == "__main__":
    test_optimizer()

# profit_guard.py
"""
Günlük kâr limiti ve otomatik durdurma modülü
"""
import os as _os
import json
import datetime
from typing import Optional

class ProfitGuard:
    def __init__(self, limit_pct: float = 4.0, state_file: str = 'profit_guard_state.json'):
        """
        limit_pct: Günlük kâr limiti (%)
        state_file: Kâr ve tarih bilgisinin saklandığı dosya
        """
        self.limit_pct = limit_pct
        self.state_file = state_file
        self._load_state()

    def _load_state(self):
        today = datetime.date.today().isoformat()
        if _os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            if state.get('date') == today:
                self.start_equity = state.get('start_equity', 0)
                self.current_equity = state.get('current_equity', 0)
                self.stopped = state.get('stopped', False)
                return
        # Yeni gün veya dosya yok
        self.start_equity = 0
        self.current_equity = 0
        self.stopped = False
        self._save_state()

    def _save_state(self):
        state = {
            'date': datetime.date.today().isoformat(),
            'start_equity': self.start_equity,
            'current_equity': self.current_equity,
            'stopped': self.stopped
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def update_equity(self, equity: float):
        """Gün başında ve her işlem sonrası equity güncellemesi."""
        if self.start_equity == 0:
            self.start_equity = equity
        self.current_equity = equity
        self._save_state()

    def check_limit(self, notify_func=None) -> bool:
        """
        Kâr limiti aşıldıysa True döner, işlemleri durdurur ve log/uyarı fırlatır.
        notify_func: Opsiyonel, limit aşımında çağrılacak fonksiyon (ör. trade engine'e mesaj)
        """
        if self.start_equity == 0:
            return False
        profit_pct = 100 * (self.current_equity - self.start_equity) / self.start_equity
        if profit_pct >= self.limit_pct:
            self.stopped = True
            self._save_state()
            msg = f"[ProfitGuard] Günlük kâr limiti aşıldı! Kâr: %{profit_pct:.2f} (Limit: %{self.limit_pct})"
            print(msg)
            try:
                import logging
                logging.warning(msg)
            except Exception:
                pass
            if notify_func:
                try:
                    notify_func(msg)
                except Exception:
                    pass
            return True
        return False

    def reset_day(self):
        """Yeni gün başında çağrılır, limiti ve equity'yi sıfırlar."""
        self.start_equity = 0
        self.current_equity = 0
        self.stopped = False
        self._save_state()

    def is_stopped(self) -> bool:
        return self.stopped

# Test fonksiyonu
def test_profit_guard():
    import tempfile
    tmpfile = tempfile.mktemp()
    pg = ProfitGuard(limit_pct=2.0, state_file=tmpfile)
    pg.update_equity(1000)
    print('Başlangıç:', pg.start_equity, pg.current_equity, pg.is_stopped())
    pg.update_equity(1010)
    print('Kâr limiti geçti mi?', pg.check_limit(), pg.is_stopped())
    pg.update_equity(1025)
    print('Kâr limiti geçti mi?', pg.check_limit(), pg.is_stopped())
    pg.reset_day()
    print('Reset sonrası:', pg.start_equity, pg.current_equity, pg.is_stopped())
    _os.remove(tmpfile)

if __name__ == "__main__":
    test_profit_guard()

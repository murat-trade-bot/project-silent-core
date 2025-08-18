# humanizer.py
"""
İnsanvari emir zamanlama ve miktar varyasyonu modülü
"""
import random
import time
from typing import Callable, Any


def random_sleep(min_sec: float = 0.3, max_sec: float = 2.0, sleep_func: Callable = time.sleep) -> float:
    """Emir öncesi rastgele bekleme (insanvari). Testte sleep_func ile mocklanabilir."""
    t = random.uniform(min_sec, max_sec)
    sleep_func(t)
    return t



def randomize_quantity(base_qty: float, pct: float = 0.05, method: str = 'uniform') -> float:
    """
    Emir miktarını varyasyonla insanlaştır. method: 'uniform', 'gauss', 'lognormal', 'exponential'
    """
    delta = base_qty * pct
    if method == 'gauss':
        qty = random.gauss(base_qty, delta/2)
        qty = max(base_qty - delta, min(base_qty + delta, qty))
    elif method == 'lognormal':
        # lognormal mean=log(base_qty), sigma=delta/base_qty
        import math
        sigma = max(0.01, delta/base_qty)
        qty = random.lognormvariate(math.log(base_qty), sigma)
        qty = max(base_qty - delta, min(base_qty + delta, qty))
    elif method == 'exponential':
        qty = random.expovariate(1/(base_qty if base_qty else 1))
        qty = max(base_qty - delta, min(base_qty + delta, qty))
    else:
        qty = random.uniform(base_qty - delta, base_qty + delta)
    return round(qty, 8)



def humanized_order_wrapper(
    order_func: Callable,
    *args,
    min_sleep=0.3,
    max_sleep=2.0,
    qty_var_pct=0.05,
    qty_arg_index=None,
    qty_var_method='uniform',
    sleep_func: Callable = time.sleep,
    log_func: Callable = None,
    active_hours: tuple = None,
    advanced_pattern: dict = None,
    **kwargs
) -> Any:
    """
    Emir fonksiyonunu insanvari sleep ve miktar varyasyonu ile sarar.
    qty_arg_index: Emir fonksiyonunda miktar argümanının sırası (None ise kwargs'tan 'qty' aranır)
    sleep_func: testte mock için
    log_func: insanlaştırılmış emir sonrası log fonksiyonu
    qty_var_method: 'uniform', 'gauss', 'lognormal', 'exponential'
    active_hours: (start_hour, end_hour) tuple'ı verilirse, sadece bu saatlerde emir atılır
    advanced_pattern: {'fast_prob': 0.2, 'fast_sleep': (0.05, 0.2)} gibi davranış kalıbı
    """
    import datetime
    # Saat aralığı kontrolü
    if active_hours is not None:
        now = time.localtime()
        if not (active_hours[0] <= now.tm_hour < active_hours[1]):
            if log_func:
                log_func({'skipped': True, 'reason': 'inactive_hour', 'timestamp': datetime.datetime.now().isoformat()})
            return {'skipped': True, 'reason': 'inactive_hour'}

    # Gelişmiş insan davranışı: %fast_prob olasılıkla çok kısa sleep uygula
    if advanced_pattern and random.random() < advanced_pattern.get('fast_prob', 0):
        min_sleep, max_sleep = advanced_pattern.get('fast_sleep', (0.05, 0.2))

    slept = random_sleep(min_sleep, max_sleep, sleep_func=sleep_func)
    # Miktar varyasyonu uygula
    qty_used = None
    if qty_arg_index is not None and len(args) > qty_arg_index:
        orig_qty = args[qty_arg_index]
        new_qty = randomize_quantity(orig_qty, qty_var_pct, method=qty_var_method)
        args = list(args)
        args[qty_arg_index] = new_qty
        args = tuple(args)
        qty_used = new_qty
    elif 'qty' in kwargs:
        kwargs['qty'] = randomize_quantity(kwargs['qty'], qty_var_pct, method=qty_var_method)
        qty_used = kwargs['qty']
    result = order_func(*args, **kwargs)
    if log_func:
        log_func({
            'slept': slept,
            'qty': qty_used,
            'timestamp': datetime.datetime.now().isoformat(),
            'symbol': args[0] if len(args) > 0 else kwargs.get('symbol'),
            'order_func': getattr(order_func, '__name__', str(order_func))
        })
    return {'result': result, 'slept': slept, 'qty': qty_used}

# Test fonksiyonu
# Test fonksiyonu


def test_humanizer():
    def dummy_order(symbol, qty):
        print(f"Order sent: {symbol}, qty={qty}")
        return {'symbol': symbol, 'qty': qty}

    logs = []
    def log_func(info):
        logs.append(info)
        print(f"LOG: {info}")

    # Mock sleep (gerçek bekleme yok)
    def fake_sleep(t):
        print(f"Fake sleep: {t:.3f}s")

    print("--- Uniform ---")
    for _ in range(2):
        out = humanized_order_wrapper(
            dummy_order, 'BTCUSDT', 0.01,
            min_sleep=0.1, max_sleep=0.5, qty_var_pct=0.1, qty_arg_index=1,
            qty_var_method='uniform', sleep_func=fake_sleep, log_func=log_func
        )
        print('Result:', out)

    print("--- Lognormal ---")
    for _ in range(2):
        out = humanized_order_wrapper(
            dummy_order, 'BTCUSDT', 0.01,
            min_sleep=0.1, max_sleep=0.5, qty_var_pct=0.1, qty_arg_index=1,
            qty_var_method='lognormal', sleep_func=fake_sleep, log_func=log_func
        )
        print('Result:', out)

    print("--- Advanced Pattern (fast sleep) ---")
    for _ in range(5):
        out = humanized_order_wrapper(
            dummy_order, 'BTCUSDT', 0.01,
            min_sleep=0.1, max_sleep=0.5, qty_var_pct=0.1, qty_arg_index=1,
            qty_var_method='gauss', sleep_func=fake_sleep, log_func=log_func,
            advanced_pattern={'fast_prob': 0.5, 'fast_sleep': (0.01, 0.05)}
        )
        print('Result:', out)

    print("--- Active Hours ---")
    # Saat dışında ise skip
    out = humanized_order_wrapper(
        dummy_order, 'BTCUSDT', 0.01,
        min_sleep=0.1, max_sleep=0.5, qty_var_pct=0.1, qty_arg_index=1,
        qty_var_method='uniform', sleep_func=fake_sleep, log_func=log_func,
        active_hours=(0, 1)  # Muhtemelen şu an dışında
    )
    print('Result:', out)

if __name__ == "__main__":
    test_humanizer()

# Yardımcı: Belirli saat aralığında emir atılabilir mi?
def is_in_active_hours(start_hour=9, end_hour=22) -> bool:
    """Şu anki saat aktif işlem aralığında mı?"""
    now = time.localtime()
    return start_hour <= now.tm_hour < end_hour

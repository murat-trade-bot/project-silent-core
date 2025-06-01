"""
Strategy Optimizer Module
Strateji parametrelerini geçmiş veriye göre optimize eder.
Stealth mod, loglama ve hata toleransı içerir.
"""

import random
from core.logger import BotLogger

logger = BotLogger()

def optimize_strategy_parameters(backtest_func=None, param_grid=None, search_type="random", max_trials=20, update_settings=False):
    """
    Strateji parametrelerini optimize eder.
    backtest_func: parametreleri alıp skor döndüren fonksiyon (zorunlu!).
    param_grid: {'STOP_LOSS_RATIO': [0.003, 0.005, 0.007], ...}
    search_type: 'random' veya 'grid'
    update_settings: True ise en iyi parametreler settings'e yazılır.
    """
    if backtest_func is None:
        logger.warning("optimize_strategy_parameters: backtest_func belirtilmedi, gerçek optimizasyon yapılmayacak!")
        return {
            "STOP_LOSS_RATIO": 0.005,
            "TAKE_PROFIT_RATIO": 0.01
        }

    # Varsayılan parametre aralığı
    default_grid = {
        "STOP_LOSS_RATIO": [0.003, 0.005, 0.007],
        "TAKE_PROFIT_RATIO": [0.008, 0.01, 0.012],
        "EMA_PERIOD": [9, 12, 21],
        "RSI_PERIOD": [14, 21]
    }
    if not param_grid:
        param_grid = default_grid
    else:
        # Eksik anahtarlar için varsayılanları ekle
        for k, v in default_grid.items():
            if k not in param_grid:
                param_grid[k] = v

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    best_params = {}
    best_score = float('-inf')
    trials = 0
    tried_combinations = set()

    def params_to_tuple(params):
        return tuple(params[k] for k in keys)

    if search_type == "grid":
        from itertools import product
        for combination in product(*values):
            params = dict(zip(keys, combination))
            params_tuple = params_to_tuple(params)
            if params_tuple in tried_combinations:
                continue
            tried_combinations.add(params_tuple)
            try:
                score = backtest_func(params)
                logger.info(f"GridSearch: Params={params}, Score={score:.4f}")
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception as e:
                logger.error(f"GridSearch error: {e}")
            trials += 1
            if trials >= max_trials:
                break
    else:  # random search
        while trials < max_trials:
            params = {k: random.choice(v) for k, v in param_grid.items()}
            params_tuple = params_to_tuple(params)
            if params_tuple in tried_combinations:
                continue
            tried_combinations.add(params_tuple)
            try:
                score = backtest_func(params)
                logger.info(f"RandomSearch: Params={params}, Score={score:.4f}")
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception as e:
                logger.error(f"RandomSearch error: {e}")
            trials += 1

    logger.info(f"Best params: {best_params}, Best score: {best_score:.4f}")

    # İstenirse settings'e yaz
    if update_settings and best_params:
        try:
            from config import settings
            for k, v in best_params.items():
                setattr(settings, k, v)
            logger.info("Best params settings'e yazıldı.")
        except Exception as e:
            logger.error(f"Settings update failed: {e}")

    return best_params if best_params else {
        "STOP_LOSS_RATIO": 0.005,
        "TAKE_PROFIT_RATIO": 0.01
    }
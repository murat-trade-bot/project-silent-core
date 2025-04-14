import time
import random
import traceback

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

logger = BotLogger()

def run_bot_cycle():
    time.sleep(random.uniform(2, 10))
    stealth.maybe_enter_sleep()
    current_mode = get_current_strategy_mode()
    risk_analyzer = GlobalRiskAnalyzer()
    risk_level = risk_analyzer.evaluate_risk_level()
    ob_analyzer = OrderBookAnalyzer()
    ob_info = ob_analyzer.analyze_liquidity_zones()
    liquidity_pressure = ob_info.get("liquidity_pressure", "neutral")

    symbol = settings.SYMBOL
    ohlcv_15m = fetch_ohlcv_from_binance(symbol, "15m", 100)
    ohlcv_1h  = fetch_ohlcv_from_binance(symbol, "1h", 100)

    sentiment = analyze_sentiment()
    onchain_data = track_onchain_activity()

    rsi_15m = macd_15m = signal_15m = None
    closes_15m = [c[4] for c in ohlcv_15m] if ohlcv_15m else []
    if len(closes_15m) >= 26:
        rsi_list_15m = calculate_rsi(closes_15m, period=14)
        if rsi_list_15m:
            rsi_15m = round(rsi_list_15m[-1], 2)
        macd_line_15m, signal_line_15m = calculate_macd(closes_15m, 12, 26, 9)
        if macd_line_15m is not None and signal_line_15m is not None:
            macd_15m = round(macd_line_15m[-1], 2)
            signal_15m = round(signal_line_15m[-1], 2)

    rsi_1h = macd_1h = signal_1h = None
    atr_value = None
    closes_1h = [c[4] for c in ohlcv_1h] if ohlcv_1h else []
    if len(closes_1h) >= 26:
        rsi_list_1h = calculate_rsi(closes_1h, period=14)
        if rsi_list_1h:
            rsi_1h = round(rsi_list_1h[-1], 2)
        macd_line_1h, signal_line_1h = calculate_macd(closes_1h, 12, 26, 9)
        if macd_line_1h is not None and signal_line_1h is not None:
            macd_1h = round(macd_line_1h[-1], 2)
            signal_1h = round(signal_line_1h[-1], 2)
        if settings.USE_ATR_STOPLOSS:
            atr_value = calculate_atr(ohlcv_1h, settings.ATR_PERIOD)
            if atr_value:
                atr_value = round(atr_value, 2)

    dynamic_position_size = get_dynamic_position_size(atr_value, settings.POSITION_SIZE_PCT)

    strategy = Strategy()
    strategy.update_context(
        mode=current_mode,
        risk=risk_level,
        pressure=liquidity_pressure,
        rsi_15m=rsi_15m,
        macd_15m=macd_15m,
        macd_signal_15m=signal_15m,
        rsi_1h=rsi_1h,
        macd_1h=macd_1h,
        macd_signal_1h=signal_1h,
        atr=atr_value
    )

    domino_signal = detect_domino_effect(closes_1h)
    selected_assets = select_coins()
    optimize_performance_infrastructure()

    decision = strategy.decide_trade()
    action = decision.get("action")
    reason = decision.get("reason", "")
    logger.log(f"[CYCLE] Mode={current_mode}, Risk={risk_level}, Press={liquidity_pressure}, "
               f"RSI15={rsi_15m}, RSI1h={rsi_1h}, MACD1h={macd_1h}/{signal_1h}, "
               f"Action={action}, Reason={reason}")

    if stealth.maybe_drop_trade():
        logger.log("[STEALTH] İşlem iptal.")
        return

    executor = ExecutorManager()
    executor.manage_position(action)

def main_loop():
    logger.log("Project Silent Core (Advanced & Üretim Seviyesi) başlatılıyor...")
    retry_count = 0
    while True:
        try:
            run_bot_cycle()
            retry_count = 0
        except Exception as e:
            logger.log("[ERROR] Döngü hatası: " + str(e))
            logger.log(traceback.format_exc())
            retry_count += 1
            if retry_count < settings.MAX_RETRIES:
                wait_time = settings.RETRY_WAIT_TIME * retry_count
                logger.log(f"[ERROR] {retry_count}. retry, {wait_time}s bekleniyor...")
                time.sleep(wait_time)
            else:
                logger.log("[ERROR] Maksimum retry sayısına ulaşıldı, manuel müdahale gerekebilir.")
                retry_count = 0

        sleep_time = max(settings.CYCLE_INTERVAL + random.randint(settings.CYCLE_JITTER_MIN, settings.CYCLE_JITTER_MAX), 10)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main_loop()

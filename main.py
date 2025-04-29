import os
import time
import random
import csv
from datetime import datetime, timedelta

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
from notifier import send_notification  # ← Telegram bildirimini ekledik

logger = BotLogger()
executor = ExecutorManager()

# --- Başlangıç Ayarları ---
START_TIME = time.time()
HEARTBEAT_INTERVAL = 3600  # saniye
CSV_FILE = settings.CSV_LOG_FILE

# --- İstatistik Değişkenleri ---
start_balance = executor.get_balance('USDT')
total_trades = 0
win_trades = 0
loss_trades = 0
trade_durations = []
peak_balance = start_balance
max_drawdown = 0.0

# Başlangıç bilgisi
dördüm = update_settings_for_period()
print(f"Bot Başlatıldı:      {datetime.utcnow()} UTC")
print(f"Başlangıç Sermayesi: {start_balance:.2f} USDT")
print(f"Hedef Sermaye:       {settings.TARGET_USDT:.2f} USDT")


def log_trade_csv(trade: dict):
    """
    Append a trade record to CSV_FILE with header if not exists.
    """
    fieldnames = ['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']
    exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            'timestamp': trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'symbol':    trade['symbol'],
            'action':    trade['action'],
            'quantity':  trade['quantity'],
            'price':     trade['price'],
            'pnl':       trade['pnl']
        })


def run_bot_cycle(symbol):
    global start_balance
    cycle_start = time.time()
    # (0) İnsanvari gecikme
    time.sleep(random.uniform(2, 10))
    cycle_time = datetime.utcnow()
    print(f"{cycle_time} [CYCLE] {symbol} için döngü başlıyor.")
    logger.log(f"[CYCLE] {symbol} için döngü başlıyor.", level="INFO")

    try:
        # (1) Stealth
        stealth.maybe_enter_sleep()

        # (2) Zaman stratejisi
        current_mode = get_current_strategy_mode()

        # (3) Küresel risk analizi
        risk_level = GlobalRiskAnalyzer().evaluate_risk_level()

        # (4) Liquidity pressure (opsiyonel)
        pressure = 'neutral'

        # --- Teknik Analiz Verileri ---
        ohlcv_15m = fetch_ohlcv_from_binance(symbol, "15m", limit=50)
        prices_15m = [c[4] for c in ohlcv_15m]
        rsi_15m = calculate_rsi(prices_15m)[-1] if prices_15m else None
        macd_15m, macd_signal_15m = calculate_macd(prices_15m)
        atr = calculate_atr(ohlcv_15m)

        ohlcv_1h = fetch_ohlcv_from_binance(symbol, "1h", limit=50)
        prices_1h = [c[4] for c in ohlcv_1h]
        rsi_1h = calculate_rsi(prices_1h)[-1] if prices_1h else None
        macd_1h, macd_signal_1h = calculate_macd(prices_1h)

        # --- Bakiye ve PnL hesaplama ---
        current_balance = executor.get_balance('USDT')
        current_pnl     = current_balance - start_balance

        # --- Strateji ve karar ---
        strategy = Strategy()
        strategy.update_context(
            symbol=symbol,
            mode=current_mode,
            risk=risk_level,
            pressure=pressure,
            # teknik analiz sinyalleri
            rsi_15m=rsi_15m,
            macd_15m=macd_15m[-1] if macd_15m else None,
            macd_signal_15m=macd_signal_15m[-1] if macd_signal_15m else None,
            rsi_1h=rsi_1h,
            macd_1h=macd_1h[-1] if macd_1h else None,
            macd_signal_1h=macd_signal_1h[-1] if macd_signal_1h else None,
            atr=atr
        )
        decision = strategy.decide_trade(current_balance, current_pnl)
        action   = decision.get("action")

        # (5) Stealth drop
        if stealth.maybe_drop_trade():
            logger.log(f"[STEALTH] {symbol} işlemi iptal edildi.", level="WARNING")
            return None

        # (6) Emir yürütme
        trade_result = executor.manage_position(symbol, action)
        return {
            'symbol':    symbol,
            'action':    trade_result.get('action'),
            'quantity':  trade_result.get('quantity'),
            'price':     trade_result.get('price'),
            'pnl':       trade_result.get('pnl'),
            'timestamp': datetime.utcnow(),
            'duration':  time.time() - cycle_start
        }

    except Exception as e:
        logger.log(f"[ERROR] Döngü hatası ({symbol}): {e}", level="ERROR")
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


if __name__ == "__main__":
    # → Performans izlemeyi başlat
    optimize_performance_infrastructure()

    retry_count    = 0
    last_heartbeat = START_TIME

    while True:
        # Her döngü başında dönem ayarlarını güncelle
        period = update_settings_for_period()

        # Altcoin seçim (dynamic / static kontrolü)
        if settings.USE_DYNAMIC_SYMBOL_SELECTION:
            symbols_to_trade = select_coins() or settings.SYMBOLS
        else:
            symbols_to_trade = settings.SYMBOLS

        for symbol in symbols_to_trade:
            result = run_bot_cycle(symbol)
            if result:
                total_trades += 1
                if result['pnl'] >= 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                trade_durations.append(result['duration'])

                print(f"{result['timestamp']} - {result['symbol']} "
                      f"{result['action']} {result['quantity']} @ {result['price']} → "
                      f"PnL: {result['pnl']:+.2f} USDT")

                # ► Telegram bildirimi
                if settings.NOTIFIER_ENABLED:
                    message = (
                        f"İşlem: {result['action']} {result['symbol']} "
                        f"@ {result['price']:.2f} USD, PnL: {result['pnl']:+.2f} USDT"
                    )
                    send_notification(message)

                log_trade_csv(result)
                print_metrics()

            # Heartbeat
            if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
                uptime = timedelta(seconds=int(time.time() - START_TIME))
                print(f"[HEARTBEAT] Bot canlı, uptime: {uptime}")
                last_heartbeat = time.time()

            time.sleep(settings.CYCLE_INTERVAL +
                       random.randint(settings.CYCLE_JITTER_MIN,
                                      settings.CYCLE_JITTER_MAX))

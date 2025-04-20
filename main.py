import os
import time
import random
import traceback
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

logger = BotLogger()
executor = ExecutorManager()

# --- Başlangıç Ayarları ---
START_TIME = time.time()
HEARTBEAT_INTERVAL = 3600  # saniye

# Initialize metrics
start_balance = executor.get_balance('USDT')
total_trades = 0
win_trades = 0
loss_trades = 0
trade_durations = []
peak_balance = start_balance
max_drawdown = 0.0

print(f"Başlangıç Sermayesi: {start_balance:.2f} USDT")
print(f"Hedef Sermaye:     {settings.TARGET_USDT:.2f} USDT")


def run_bot_cycle(symbol):
    cycle_start = time.time()
    # (0) İnsanvari gecikme
    time.sleep(random.uniform(2, 10))
    logger.log(f"[CYCLE] {symbol} için döngü başlıyor.", level="INFO")
    try:
        # (1) Stealth: Rastgele uyuma
        stealth.maybe_enter_sleep()

        # (2) Zaman stratejisi (özel günler dahil)
        current_mode = get_current_strategy_mode()

        # (3) Küresel risk analizi
        risk_analyzer = GlobalRiskAnalyzer()
        risk_level = risk_analyzer.evaluate_risk_level()

        # ... [Diğer modüller aynen çalışır] ...

        # Strateji karar mekanizması
        strategy = Strategy()
        decision = strategy.decide_trade()
        action = decision.get("action")

        # Stealth kontrolü
        if stealth.maybe_drop_trade():
            logger.log(f"[STEALTH] {symbol} işlemi iptal edildi.", level="WARNING")
            return None

        # Emir yürütme ve sonuç
        trade_result = executor.manage_position(symbol, action)
        return {
            'symbol': symbol,
            'action': trade_result.get('action'),
            'quantity': trade_result.get('quantity'),
            'price': trade_result.get('price'),
            'pnl': trade_result.get('pnl'),
            'timestamp': datetime.utcnow(),
            'duration': time.time() - cycle_start,
            'risk': risk_level
        }

    except Exception as e:
        logger.log(f"[ERROR] Döngü hatası ({symbol}): {e}", level="ERROR")
        return None


def print_metrics():
    global peak_balance, max_drawdown
    # Update peak and drawdown
    curr_balance = executor.get_balance('USDT')
    peak_balance = max(peak_balance, curr_balance)
    drawdown = peak_balance - curr_balance
    max_drawdown = max(max_drawdown, drawdown)

    pnl = curr_balance - start_balance
    pnl_pct = (pnl / start_balance * 100) if start_balance else 0
    progress_pct = (curr_balance / settings.TARGET_USDT * 100)
    avg_duration = (sum(trade_durations) / len(trade_durations)) if trade_durations else 0
    win_rate = (win_trades / total_trades * 100) if total_trades else 0

    print(f"Anlık Sermaye:       {curr_balance:.2f} USDT")
    print(f"Toplam PnL:          {pnl:.2f} USDT ({pnl_pct:+.2f}%)")
    print(f"Hedefe Progress:     {progress_pct:.4f}%")
    print(f"Toplam İşlem:        {total_trades}  Kazanan: {win_trades}  ({win_rate:.1f}%)")
    print(f"Max Drawdown:        {max_drawdown:.2f} USDT")
    print(f"Ortalama Trade Süre: {avg_duration:.1f}s")


if __name__ == "__main__":
    print(f"Bot Başlatıldı:      {datetime.utcnow()} UTC")
    logger.log("Project Silent Core (Üretim ve Test Seviyesi) başlatılıyor...")
    retry_count = 0
    last_heartbeat = START_TIME

    while True:
        for symbol in settings.SYMBOLS:
            result = run_bot_cycle(symbol)
            if result:
                total_trades += 1
                if result['pnl'] >= 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                trade_durations.append(result['duration'])

                # İşlem Detayı
                print(f"{result['timestamp']} - {result['symbol']} {result['action']} {result['quantity']} @ {result['price']} → PnL: {result['pnl']:+.2f} USDT")

                # Güncel metrikleri yaz
                print_metrics()

            # Heartbeat
            if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
                uptime = timedelta(seconds=int(time.time() - START_TIME))
                print(f"[HEARTBEAT] Bot canlı, uptime: {uptime}")
                last_heartbeat = time.time()

            # Retry ve bekleme
            time.sleep(settings.CYCLE_INTERVAL + random.randint(settings.CYCLE_JITTER_MIN, settings.CYCLE_JITTER_MAX))
        
        # Opsiyonel: testnet ya da paper trading kontrolü
        if settings.PAPER_TRADING:
            continue
        # Hata yönetimi vs.

# -*- coding: utf-8 -*-
"""
Project Silent Core - main.py (v2.3)
- Tek giriş noktası
- SIM/LIVE yürütme modu
- On-chain + teknik sinyal karar birleştirme
- Adım kurallarına (LOT_SIZE/PRICE_FILTER) uyumlu miktar/fiyat hesaplama
- Gün sonu otomatik reset + JSONL/CSV raporlama (DailyReporter)
- Stop-loss / Take-profit kapanışlarında muhasebe
- Emir öncesi risk + komisyon/slippage/likidite kontrolleri (OrderExecutor + RiskManager)
- Hata yakalama ve güvenli bildirimler
"""

from __future__ import annotations
import os
import sys
import time
import json
import math
import random
from datetime import datetime, date
from typing import Dict, Tuple, Any

from dotenv import load_dotenv
load_dotenv()

# --- Proje içi modüller ---
from binance.client import Client
from notifier import send_notification
from config import settings
from config import BAŞLANGIÇ_SERMEYESİ, IŞLEM_MIKTARI, TRADE_INTERVAL, MIN_BAKIYE, STOP_LOSS_RATIO, TAKE_PROFIT_RATIO
from core.logger import BotLogger
from modules.strategy_optimizer import optimize_strategy_parameters
from onchain_alternative import get_trade_signal
from modules.order_executor import OrderExecutor
from modules.risk_manager import RiskManager
from modules.daily_reporter import DailyReporter
from modules.signals import detect_buy_signal, detect_sell_signal, detect_trend_reversal_sell
from utils.signal_utils import calculate_rsi, calculate_ema

logger = BotLogger()

# Kullanılacak coin listesi
TRADE_SYMBOL_LIST = [
    "RVNUSDT", "MASKUSDT", "PEPEUSDT", "ADAUSDT", "SOLUSDT",
    "XRPUSDT", "DOGEUSDT", "TRXUSDT", "SUIUSDT"
]

COIN_ID_MAP = {
    "RVNUSDT": "ravencoin",
    "MASKUSDT": "mask-network",
    "PEPEUSDT": "pepe",
    "ADAUSDT": "cardano",
    "SOLUSDT": "solana",
    "XRPUSDT": "ripple",
    "DOGEUSDT": "dogecoin",
    "TRXUSDT": "tron",
    "SUIUSDT": "sui"
}

# --- Volatilite ve hacim eşikleri (baseline, proje ihtiyaçlarına göre ayarla) ---
VOLATILITY_THRESHOLD_1M = 0.001  # %0.1
VOLATILITY_THRESHOLD_5M = 0.002  # %0.2
VOLUME_THRESHOLD_1M = 5_000      # 1 dakikalık quote hacim için approx. (pariteye göre ayarla)
VOLUME_THRESHOLD_5M = 20_000     # 5 dakikalık quote hacim için approx.
SLIPPAGE_LIMIT = 0.005           # %0.5

MAX_RETRIES = 3
RETRY_DELAY = 2  # saniye

# --- Yürütme modları ---
EXECUTION_MODE = getattr(settings, "EXECUTION_MODE", os.getenv("EXECUTION_MODE", "SIM")).upper()  # "SIM" | "LIVE"
TESTNET_MODE = getattr(settings, "TESTNET_MODE", False)
NOTIFIER_ENABLED = getattr(settings, "NOTIFIER_ENABLED", False)

# === Binance Client init ===
def initialize_client(retries: int = 3, delay: int = 5) -> Client:
    for attempt in range(1, retries + 1):
        try:
            client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
            if TESTNET_MODE:
                client.API_URL = 'https://testnet.binance.vision/api'
                logger.info("Testnet mode enabled")
            else:
                logger.info("Live mode enabled")
            return client
        except Exception as e:
            logger.error(f"Binance client başlatılamadı (deneme {attempt}/{retries}): {e}")
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                err_msg = f"Failed to initialize Binance client after {retries} attempts: {e}"
                logger.critical(err_msg)
                if NOTIFIER_ENABLED:
                    try:
                        send_notification(f"[CRITICAL] {err_msg}")
                    except Exception:
                        pass
                sys.exit(1)

# === Market yardımcıları ===
def get_current_price(client: Client, symbol: str) -> float | None:
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        logger.error(f"Fiyat alınamadı ({symbol}): {e}")
        return None


def get_symbol_filters(client: Client, symbol: str) -> Dict[str, Any]:
    """LOT_SIZE / PRICE_FILTER / MIN_NOTIONAL değerlerini döndür."""
    try:
        info = client.get_symbol_info(symbol)
        filters = {f['filterType']: f for f in info.get('filters', [])}
        return filters
    except Exception as e:
        logger.warning(f"Sembol filtresi alınamadı ({symbol}): {e}")
        return {}


def floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.floor(value / step) * step


def quantize_qty_price(client: Client, symbol: str, qty: float, price: float) -> Tuple[float, float]:
    """Miktar ve fiyatı borsa adımlarına uydur."""
    filters = get_symbol_filters(client, symbol)
    lot = filters.get('LOT_SIZE', {})
    pf = filters.get('PRICE_FILTER', {})

    step_size = float(lot.get('stepSize', '0.00000001')) if lot else 0.00000001
    tick_size = float(pf.get('tickSize', '0.00000001')) if pf else 0.00000001

    q = floor_to_step(qty, step_size)
    p = floor_to_step(price, tick_size)

    # MIN_NOTIONAL kontrolü (varsa)
    mn = filters.get('MIN_NOTIONAL', {})
    try:
        min_notional = float(mn.get('minNotional')) if mn else None
        if min_notional and q * p < min_notional:
            needed_qty = (min_notional / p) * 1.001
            q = floor_to_step(needed_qty, step_size)
    except Exception:
        pass

    return q, p


# === Fırsat taraması ===
def analyze_coin_opportunity(client: Client, symbol: str) -> Tuple[float, Dict[str, float]]:
    """Volatilite * hacim / spread skorunu hesapla."""
    try:
        klines = client.get_klines(symbol=symbol, interval='1m', limit=5)
        close_prices = [float(k[4]) for k in klines]
        if len(close_prices) < 2:
            return 0.0, {}
        volatility = (max(close_prices) - min(close_prices)) / close_prices[0]

        ticker = client.get_ticker(symbol=symbol)
        volume = float(ticker.get('quoteVolume', 0.0))  # quote hacim

        order_book = client.get_order_book(symbol=symbol, limit=5)
        bid = float(order_book['bids'][0][0])
        ask = float(order_book['asks'][0][0])
        spread = (ask - bid) / bid if bid > 0 else 0

        score = volatility * volume / (spread + 0.0001)
        details = {"volatility": volatility, "volume": volume, "spread": spread, "score": score}
        return score, details
    except Exception as e:
        logger.warning(f"{symbol} için fırsat analizi yapılamadı: {e}")
        return 0.0, {}


def get_volatility_and_volume(client: Client, symbol: str) -> Tuple[float, float, float, float]:
    """Son 1dk ve 5dk volatilite ve hacim."""
    try:
        klines_1m = client.get_klines(symbol=symbol, interval='1m', limit=5)
        closes = [float(k[4]) for k in klines_1m]
        vols = [float(k[5]) for k in klines_1m]  # base volume olabilir; approx
        if len(closes) < 5:
            return 0.0, 0.0, 0.0, 0.0
        vol_1m = vols[-1]
        vol_5m = sum(vols)
        volat_1m = abs(closes[-1] - closes[-2]) / closes[-2] if closes[-2] != 0 else 0
        volat_5m = (max(closes) - min(closes)) / closes[0] if closes[0] != 0 else 0
        return volat_1m, volat_5m, vol_1m, vol_5m
    except Exception as e:
        logger.warning(f"{symbol} için volatilite/hacim hesaplanamadı: {e}")
        return 0.0, 0.0, 0.0, 0.0


# === On-chain sinyal güvenli çağrı ===
def safe_get_trade_signal(symbol: str, coin_id: str) -> Dict[str, Any] | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_trade_signal(symbol, coin_id)
        except Exception as e:
            msg = str(e)
            rate_limited = False
            try:
                rate_limited = (hasattr(e, "response") and getattr(e.response, "status_code", None) == 429) or ("429" in msg or "Too Many Requests" in msg)
            except Exception:
                pass
            if rate_limited:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                    continue
                else:
                    logger.warning(f"Rate limit aşıldı, sinyal atlanıyor: {symbol}")
                    return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
            else:
                logger.error(f"Sinyal alınırken hata: {e}")
                return None


def check_slippage(expected_price: float, actual_price: float) -> bool:
    if expected_price == 0:
        return False
    slippage = abs(actual_price - expected_price) / expected_price
    return slippage > SLIPPAGE_LIMIT


# === Karar birleştirici ===
def decide_action(symbol: str, onchain: Dict[str, Any], tech: Dict[str, Any], has_position: bool) -> Tuple[str, str]:
    """On-chain ve teknik göstergeleri birleştirerek nihai karar döndür: (BUY/SELL/WAIT, reason)"""
    raw_signal = (onchain or {}).get("trade_signal", "WAIT")

    tech_buy = tech.get("buy", False)
    tech_sell = tech.get("sell", False) or tech.get("strong_reversal", False)

    if raw_signal == "BUY" and tech_buy and not has_position:
        return "BUY", "On-chain BUY + teknik BUY"
    if (raw_signal == "SELL" and has_position) or tech_sell:
        if has_position:
            return "SELL", "On-chain SELL veya teknik SELL"
        else:
            return "WAIT", "SELL sinyali var ama pozisyon yok"
    return "WAIT", "Sinyaller uyumsuz veya koşullar sağlanmadı"


# === Ana uygulama ===
def main() -> None:
    print("Project Silent Core v2.3 Başladı")
    print(f"Başlangıç Sermayesi: {BAŞLANGIÇ_SERMEYESİ} USDT")
    print(f"Çalışma Modu: Binance SPOT | EXECUTION_MODE={EXECUTION_MODE} | TESTNET={TESTNET_MODE}")
    print(f"İşlem Yapılacak Coinler: {', '.join(TRADE_SYMBOL_LIST)}")
    print("-" * 42)

    client = initialize_client()

    # Strateji optimizasyonu (opsiyonel)
    try:
        optimize_strategy_parameters()
    except Exception as e:
        logger.warning(f"Strategy optimization failed: {e}")

    # Simülasyon muhasebesi (yaklaşık equity akışı)
    simule_bakiye = float(BAŞLANGIÇ_SERMEYESİ)

    # Risk yöneticisi + yürütücü
    risk_manager = RiskManager(day_start_equity_usdt=simule_bakiye)
    order_executor = OrderExecutor(client, risk_manager=risk_manager)

    # Günlük raporlayıcı
    reporter = DailyReporter(report_dir="reports", basename="daily_report", start_equity=simule_bakiye, logger=logger)

    # Pozisyonlar
    portfolio: Dict[str, Dict[str, Any]] = {
        coin: {
            "quantity": 0.0,
            "avg_buy_price": 0.0,
            "total_invested": 0.0,
            "has_position": False,
            "last_action": None,
            "trade_count": 0,
        } for coin in TRADE_SYMBOL_LIST
    }

    # İstatistikler
    total_trades = 0
    successful_trades = 0
    total_profit = 0.0
    daily_profit = 0.0

    protection_mode = False

    while True:
        try:
            # --- Equity'yi güncelle (rapor için) ---
            reporter.set_equity(simule_bakiye)

            # === Dinamik coin skorlama ===
            coin_scores: Dict[str, float] = {}
            coin_details: Dict[str, Dict[str, float]] = {}
            for symbol in TRADE_SYMBOL_LIST:
                score, details = analyze_coin_opportunity(client, symbol)
                coin_scores[symbol] = score
                coin_details[symbol] = details

            best_coin = max(coin_scores, key=coin_scores.get)
            best_score = coin_scores.get(best_coin, 0.0)
            best_details = coin_details.get(best_coin, {})

            # === Volatilite/hacim filtresi ===
            volat_1m, volat_5m, vol_1m, vol_5m = get_volatility_and_volume(client, best_coin)
            if (volat_1m < VOLATILITY_THRESHOLD_1M or volat_5m < VOLATILITY_THRESHOLD_5M or
                vol_1m < VOLUME_THRESHOLD_1M or vol_5m < VOLUME_THRESHOLD_5M):
                print(f"{best_coin}: Volatilite/hacim düşük, işlem yok. (1mV: {volat_1m:.4f}, 5mV: {volat_5m:.4f}, 1mH: {vol_1m:.0f}, 5mH: {vol_5m:.0f})")
                time.sleep(random.randint(10, 60))
                # Gün sonu rollover
                rolled = reporter.maybe_rollover(now=datetime.now(), total_profit_usdt=total_profit)
                if rolled:
                    protection_mode = False
                    daily_profit = 0.0
                continue

            # === Günlük kâr kilidi ===
            start_eq = reporter.start_equity if hasattr(reporter, 'start_equity') else float(BAŞLANGIÇ_SERMEYESİ)
            daily_profit_pct = (simule_bakiye - start_eq) / max(start_eq, 1e-9) * 100
            if daily_profit_pct >= 6.0 and not protection_mode:
                print("\n=== Kâr Kilidi Aktif! Günlük %6 hedefe ulaşıldı, işlemler durduruldu. ===")
                logger.info("Kâr kilidi aktif: Günlük %6 kâr hedefi aşıldı, koruma moduna geçildi.")
                if NOTIFIER_ENABLED:
                    try:
                        send_notification("🔒 Kâr kilidi aktif! Günlük %6 ulaşıldı, işlemler durduruldu.")
                    except Exception:
                        pass
                protection_mode = True

            if protection_mode:
                print(f"{best_coin}: Kâr kilidi aktif, işlem yapılmıyor.")
                time.sleep(random.randint(10, 60))
                rolled = reporter.maybe_rollover(now=datetime.now(), total_profit_usdt=total_profit)
                if rolled:
                    protection_mode = False
                    daily_profit = 0.0
                continue

            # === Teknik veri hazırlığı ===
            klines_1m = client.get_klines(symbol=best_coin, interval='1m', limit=10)
            closes_1m = [float(k[4]) for k in klines_1m]
            volumes_1m = [float(k[5]) for k in klines_1m]
            candles_1m = [{'open': float(k[1]), 'close': float(k[4])} for k in klines_1m]

            klines_3m = client.get_klines(symbol=best_coin, interval='3m', limit=3)
            candles_3m = [{'open': float(k[1]), 'close': float(k[4])} for k in klines_3m]

            rsi_values = calculate_rsi(closes_1m, period=9)
            ema_9 = calculate_ema(closes_1m, period=9)
            ema_21 = calculate_ema(closes_1m, period=21)

            tech = {
                "buy": bool(detect_buy_signal(candles_1m, candles_3m, volumes_1m)),
                "sell": bool(detect_sell_signal(candles_1m, candles_3m, volumes_1m)),
                "strong_reversal": bool(detect_trend_reversal_sell(candles_1m, rsi_values, ema_9, ema_21)),
            }

            # === On-chain sinyal ===
            analysis_result = safe_get_trade_signal(best_coin, COIN_ID_MAP.get(best_coin, "bitcoin")) or {}

            current_position = portfolio[best_coin]
            final_decision, decision_reason = decide_action(best_coin, analysis_result, tech, current_position["has_position"])

            işlem_sonucu = "WAIT ⏸️"
            executed = False
            current_price = get_current_price(client, best_coin)

            if final_decision == "BUY" and current_price:
                # IŞLEM_MIKTARI USDT tutarını miktara çevir
                qty_raw = float(IŞLEM_MIKTARI) / current_price
                qty, price_q = quantize_qty_price(client, best_coin, qty_raw, current_price)
                if qty <= 0:
                    print(f"{best_coin}: Min. notional/lot sağlanamadı, BUY atlandı.")
                else:
                    fee = 0.0
                    if EXECUTION_MODE == "LIVE":
                        try:
                            res = order_executor.execute_order(best_coin, "BUY", qty, order_type="MARKET")
                            if not res.get("ok"):
                                işlem_sonucu = f"BUY Reddedildi ⛔ ({res.get('reason')})"
                                executed = False
                            else:
                                fill_price = res.get("avg_fill_price") or current_price
                                fee = float(res.get("fee_usdt", 0.0))
                                cost = qty * fill_price + fee
                                simule_bakiye -= cost  # approx equity akışı
                                current_position.update({
                                    "quantity": qty,
                                    "avg_buy_price": fill_price,
                                    "total_invested": qty * fill_price,
                                    "has_position": True,
                                    "last_action": "BUY",
                                })
                                işlem_sonucu = "BUY Executed ✅"
                                executed = True
                        except Exception as e:
                            logger.error(f"Emir gönderilemedi (BUY {best_coin}): {e}")
                    else:
                        fill_price = current_price
                        cost = qty * fill_price
                        simule_bakiye -= cost
                        current_position.update({
                            "quantity": qty,
                            "avg_buy_price": fill_price,
                            "total_invested": cost,
                            "has_position": True,
                            "last_action": "BUY",
                        })
                        işlem_sonucu = "BUY Executed ✅"
                        executed = True
                        fee = 0.0

                    # Raporla
                    if executed:
                        reporter.log_trade(
                            symbol=best_coin,
                            side="BUY",
                            qty=qty,
                            price=current_position["avg_buy_price"],
                            fee_usdt=fee,
                            notional_usdt=qty * current_position["avg_buy_price"],
                            profit_usdt=None,
                            success=None,
                        )

            elif final_decision == "SELL" and current_price and current_position["has_position"]:
                qty_pos = current_position["quantity"]
                qty, price_q = quantize_qty_price(client, best_coin, qty_pos, current_price)
                if qty <= 0:
                    print(f"{best_coin}: Miktar 0, SELL atlandı.")
                else:
                    fee = 0.0
                    if EXECUTION_MODE == "LIVE":
                        try:
                            res = order_executor.execute_order(best_coin, "SELL", qty, order_type="MARKET")
                            if not res.get("ok"):
                                işlem_sonucu = f"SELL Reddedildi ⛔ ({res.get('reason')})"
                                executed = False
                            else:
                                fill_price = res.get("avg_fill_price") or current_price
                                fee = float(res.get("fee_usdt", 0.0))
                                sell_amount = qty * fill_price - fee
                                invested = current_position["total_invested"] * (qty / max(current_position["quantity"], 1e-9))
                                profit = sell_amount - invested
                                simule_bakiye += sell_amount
                                total_profit += profit
                                daily_profit += profit

                                # Pozisyonu kapat / azalt
                                remaining_qty = current_position["quantity"] - qty
                                if remaining_qty <= 1e-12:
                                    current_position.update({
                                        "quantity": 0.0,
                                        "avg_buy_price": 0.0,
                                        "total_invested": 0.0,
                                        "has_position": False,
                                        "last_action": "SELL",
                                    })
                                else:
                                    current_position.update({
                                        "quantity": remaining_qty,
                                        "total_invested": max(current_position["total_invested"] - invested, 0.0),
                                        "last_action": "SELL",
                                    })
                                işlem_sonucu = f"SELL Executed ✅ (Profit: {profit:.2f} USDT)"
                                executed = True
                        except Exception as e:
                            logger.error(f"Emir gönderilemedi (SELL {best_coin}): {e}")
                    else:
                        fill_price = current_price
                        sell_amount = qty * fill_price
                        invested = current_position["total_invested"] * (qty / max(current_position["quantity"], 1e-9))
                        profit = sell_amount - invested
                        simule_bakiye += sell_amount
                        total_profit += profit
                        daily_profit += profit

                        # Pozisyonu kapat / azalt
                        remaining_qty = current_position["quantity"] - qty
                        if remaining_qty <= 1e-12:
                            current_position.update({
                                "quantity": 0.0,
                                "avg_buy_price": 0.0,
                                "total_invested": 0.0,
                                "has_position": False,
                                "last_action": "SELL",
                            })
                        else:
                            current_position.update({
                                "quantity": remaining_qty,
                                "total_invested": max(current_position["total_invested"] - invested, 0.0),
                                "last_action": "SELL",
                            })
                        işlem_sonucu = f"SELL Executed ✅ (Profit: {profit:.2f} USDT)"
                        executed = True
                        fee = 0.0

                    # Raporla
                    if executed:
                        reporter.log_trade(
                            symbol=best_coin,
                            side="SELL",
                            qty=qty,
                            price=fill_price,
                            fee_usdt=fee,
                            notional_usdt=qty * fill_price,
                            profit_usdt=profit,
                            success=(profit > 0),
                        )

            # Stop-loss / Take-profit (yalnızca pozisyon varken)
            if current_position["has_position"]:
                avg_buy = current_position["avg_buy_price"]
                if avg_buy and current_price:
                    stop_loss_price = avg_buy * (1 - float(STOP_LOSS_RATIO))
                    take_profit_price = avg_buy * (1 + float(TAKE_PROFIT_RATIO))
                    if current_price <= stop_loss_price or current_price >= take_profit_price:
                        qty = current_position["quantity"]
                        qty, _ = quantize_qty_price(client, best_coin, qty, current_price)
                        if qty > 0:
                            fee = 0.0
                            if EXECUTION_MODE == "LIVE":
                                try:
                                    res = order_executor.execute_order(best_coin, "SELL", qty, order_type="MARKET")
                                    if res.get("ok"):
                                        fill_price = res.get("avg_fill_price") or current_price
                                        fee = float(res.get("fee_usdt", 0.0))
                                    else:
                                        logger.error(f"SL/TP satış reddedildi ({best_coin}): {res.get('reason')}")
                                        fill_price = current_price
                                except Exception as e:
                                    logger.error(f"SL/TP satış başarısız ({best_coin}): {e}")
                                    fill_price = current_price
                            else:
                                fill_price = current_price

                            # Muhasebe (SIM ve approx LIVE)
                            sell_amount = qty * fill_price - fee
                            invested = current_position["total_invested"]
                            profit = sell_amount - invested
                            simule_bakiye += sell_amount
                            total_profit += profit
                            daily_profit += profit
                            current_position.update({
                                "quantity": 0.0,
                                "avg_buy_price": 0.0,
                                "total_invested": 0.0,
                                "has_position": False,
                                "last_action": "SELL",
                            })
                            logger.info(("TAKE-PROFIT" if current_price >= take_profit_price else "STOP-LOSS") + f" tetiklendi: {best_coin}, fiyat: {current_price}")

                            # Raporla
                            reporter.log_trade(
                                symbol=best_coin,
                                side="SELL",
                                qty=qty,
                                price=fill_price,
                                fee_usdt=fee,
                                notional_usdt=qty * fill_price,
                                profit_usdt=profit,
                                success=(profit > 0),
                            )

            # İstatistik & loglar
            total_trades += 1
            daily_cum_profit_pct = (simule_bakiye - start_eq) / max(start_eq, 1e-9) * 100
            log_msg = (
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                f"{best_coin:<8} | Karar: {final_decision:<4} | "
                f"Bakiye: {simule_bakiye:8.2f} USDT | "
                f"Toplam Kâr: {total_profit:+7.2f} ({(total_profit/BAŞLANGIÇ_SERMEYESİ)*100:+5.1f}%) | "
                f"Günlük Kümülatif Kâr: {daily_cum_profit_pct:+5.2f}% | "
                f"İşlem Sayısı: {portfolio[best_coin]['trade_count']}"
            )
            print(log_msg)

            onchain_data = analysis_result.get('onchain_data', {}) if analysis_result else {}
            ws = onchain_data.get('whale_score', analysis_result.get('whale_score', 0))
            ts = onchain_data.get('twitter_sentiment', analysis_result.get('twitter_sentiment', 0))
            pt = onchain_data.get('price_trend', analysis_result.get('price_trend', 0))
            print(f"whale_score: {ws}, twitter_sentiment: {ts}, price_trend: {pt}")
            print(f"Fırsat Skoru: {best_score:.4f} | Volatilite: {best_details.get('volatility',0):.4f} | Hacim(q): {best_details.get('volume',0):.2f} | Spread: {best_details.get('spread',0):.6f}")
            print(f"Güncel Bakiye: {simule_bakiye:.2f} USDT")
            print(f"Trade Döngüsü: {total_trades}")
            pos = 'VAR' if current_position['has_position'] else 'YOK'
            print(f"Pozisyon Durumu: {pos}")
            print(f"Trade Kararı: {final_decision}")
            print(f"Karar Sebebi: {decision_reason}")
            print(f"İşlem Sonucu: {işlem_sonucu}")
            print(f"Son İşlem Zamanı: {datetime.now():%Y-%m-%d %H:%M}")
            print(f"Toplam Kâr: {total_profit:+.2f} USDT ({(total_profit/BAŞLANGIÇ_SERMEYESİ)*100:+.1f}%)")
            print(f"Bugünkü Kâr: {daily_profit:+.2f} USDT")
            print(f"Bugün Alım/Satım: {reporter.summary['buy_count']}/{reporter.summary['sell_count']} | Başarılı İşlem: {reporter.summary['success_trades']}")
            print("-" * 42)

            # Minimum bakiye koruması (sim approx)
            if simule_bakiye < float(MIN_BAKIYE):
                print(f"Bakiye {MIN_BAKIYE} USDT altına düştü, işlem durduruldu.")
                break

            # Gün sonu rollover (tarih değişimiyle)
            rolled = reporter.maybe_rollover(now=datetime.now(), total_profit_usdt=total_profit)
            if rolled:
                protection_mode = False
                daily_profit = 0.0
                # Yeni gün için risk yöneticisinin başlangıç equity'sini güncelle
                risk_manager.day_start_equity = reporter.start_equity

            # Rastgele bekleme (insansı davranış)
            time.sleep(random.randint(10, 60))

        except Exception as e:
            logger.critical(f"Engine crashed: {e}")
            if NOTIFIER_ENABLED:
                try:
                    send_notification(f"🚨 BOT HATASI: {e}")
                except Exception:
                    pass
            time.sleep(3)


if __name__ == "__main__":
    main()

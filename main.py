from __future__ import annotations
import os as _os
from dotenv import load_dotenv
import traceback
import types
load_dotenv()
import sys
import time
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, Tuple, Any

# Koruyucu sağlık kontrolü: os gerçekten modül mü?
assert isinstance(_os, types.ModuleType), "os gölgelendi: modül bekleniyordu"

# .env yükleyici (paket yoksa sessizce geç)
def _load_env_via_importlib():
	try:
		import importlib
		dotenv = importlib.import_module("dotenv")
		getattr(dotenv, "load_dotenv", lambda *a, **k: None)()
	except Exception:
		pass

_load_env_via_importlib()
"""dotenv yükleme importlib ile yapıldı"""

# --- Proje içi modüller ---
import importlib
try:
	_binance_client_mod = importlib.import_module("binance.client")
	_BinanceClient = getattr(_binance_client_mod, "Client", None)
except Exception:
	_BinanceClient = None

from modules import coin_scanner  # [scanner] thresholds çıktısını tetikler
from notifier import send_notification
from config import settings
from config import BAŞLANGIÇ_SERMEYESİ, IŞLEM_MIKTARI, TRADE_INTERVAL, MIN_BAKIYE, STOP_LOSS_RATIO, TAKE_PROFIT_RATIO
from core.logger import BotLogger
from core.logger import log_exceptions, logger
from core.pipeline import PIPELINE_ENABLED, build_order_plan_from_signals, validate_order_plan, execute_order_plan, execute_with_filters
from core.envcheck import load_runtime_config, assert_live_prereqs
from core.metrics import start_metrics_server_if_enabled
from core.types import SignalBundle
import os as _pipeline_os

PIPELINE_LOG_ON = _pipeline_os.getenv("ORDER_PIPELINE_LOG", "1") in ("1", "true", "yes", "on")

# --- Runtime bootstrap ---
cfg = load_runtime_config()
if cfg.mode.name == "LIVE":
	assert_live_prereqs()
start_metrics_server_if_enabled()

@log_exceptions("main-loop")
def maybe_pipeline_entry(signal_data: dict):
	if not PIPELINE_ENABLED:
		return
	sb = SignalBundle(
		symbol=signal_data.get("symbol", "BTCUSDT"),
		buy_score=float(signal_data.get("buy_score", 0.0)),
		sell_score=float(signal_data.get("sell_score", 0.0)),
		regime_on=bool(signal_data.get("regime_on", True)),
		volatility=float(signal_data.get("volatility", 0.0)),
		extras=signal_data
	)
	plan = build_order_plan_from_signals(sb)
	if plan is None:
		if PIPELINE_LOG_ON:
			logger.info("PIPELINE: WAIT (no plan)")
		return
	r = validate_order_plan(plan, market_state=None, account_state=None)
	if not r.ok:
		logger.info(f"PIPELINE: REJECTED -> {r.reasons}")
		return
	res = execute_with_filters(plan, market_state=None, account_state=None)
	if PIPELINE_LOG_ON:
		logger.info(f"PIPELINE: EXEC status={res.status} success={res.success}")
from modules.strategy_optimizer import optimize_strategy_parameters
from onchain_alternative import get_trade_signal
from modules.order_executor import OrderExecutor
from modules.risk_manager import RiskManager
from modules.daily_reporter import DailyReporter
from modules.signals import detect_buy_signal, detect_sell_signal, detect_trend_reversal_sell, safe_exit_signal, micro_entry_signal
from utils.signal_utils import calculate_rsi, calculate_ema
from modules import playbook
from modules import order_filters
from modules import humanizer

logger = BotLogger()

# --- Fallback davranışı ve alım güvenliği (env) ---
MAX_SPREAD = float(_os.getenv("MAX_SPREAD", "0.0010"))
FORCE_SCORE_LOG10 = float(_os.getenv("FORCE_SCORE_LOG10", "10.3"))
FALLBACK_COOLDOWN_SEC = int(_os.getenv("FALLBACK_COOLDOWN_SEC", "300"))
MIN_SAFE_BAL_AFTER_BUY = float(_os.getenv("MIN_SAFE_BAL_AFTER_BUY", "10"))
# Fallback kararının (şartlar uygunsa) doğrudan alım yapmasına izin ver
FALLBACK_EXECUTE = (_os.getenv("FALLBACK_EXECUTE", "True").lower() == "true")

# Fallback ve pozisyon koruma durumu
_last_fallback_buy_ts: Dict[str, int] = {}
_in_position: Dict[str, bool] = {}

# Kullanılacak coin listesi
TRADE_SYMBOL_LIST = [
	"RVNUSDT", "MASKUSDT", "PEPEUSDT", "ADAUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "TRXUSDT", "SUIUSDT"
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
EXECUTION_MODE = getattr(settings, "EXECUTION_MODE", _os.getenv("EXECUTION_MODE", "SIM")).upper()  # "SIM" | "LIVE"
TESTNET_MODE = getattr(settings, "TESTNET_MODE", False)
NOTIFIER_ENABLED = getattr(settings, "NOTIFIER_ENABLED", False)

# === İlk fırsatta satış konfigleri ===
FIRST_EXIT_MODE = (_os.getenv("FIRST_EXIT_MODE", "True").lower() == "true")
FIRST_EXIT_MIN_PROFIT_PCT = float(_os.getenv("FIRST_EXIT_MIN_PROFIT_PCT", "0.0035"))
FIRST_EXIT_MAX_HOLD_SEC = int(_os.getenv("FIRST_EXIT_MAX_HOLD_SEC", "1800"))
HARD_STOP_LOSS_PCT = float(_os.getenv("HARD_STOP_LOSS_PCT", "0.006"))
ENTRY_COOLDOWN_SEC = int(_os.getenv("ENTRY_COOLDOWN_SEC", "20"))

# --- Esnek giriş/scalp ayarları ---
SCALP_MODE_ENABLED = (_os.getenv("SCALP_MODE_ENABLED", "True").lower() == "true")
ORDERBOOK_MIN_RATIO = float(_os.getenv("ORDERBOOK_MIN_RATIO", "0.52"))
ENTRY_STRICT = (_os.getenv("ENTRY_STRICT", "False").lower() == "true")
MICRO_ENTRY_ENABLED = (_os.getenv("MICRO_ENTRY_ENABLED", "True").lower() == "true")
MICRO_ENTRY_MIN_VOLATILITY = float(_os.getenv("MICRO_ENTRY_MIN_VOLATILITY", "0.0009"))
RISK_PCT = float(_os.getenv("RISK_PCT", "0.0105"))
MIN_NOTIONAL_USDT = float(_os.getenv("MIN_NOTIONAL_USDT", "6.0"))


@dataclass
class PositionCtx:
	in_pos: bool = False
	symbol: str | None = None
	entry_price: float | None = None
	qty: float | None = None
	stop_price: float | None = None
	entry_ts: float | None = None
	last_action_ts: float = 0.0


pos = PositionCtx()


def reset_pos():
	pos.in_pos = False
	pos.symbol = None
	pos.entry_price = None
	pos.qty = None
	pos.stop_price = None
	pos.entry_ts = None
	pos.last_action_ts = 0.0


# Tür güvenliği: pos tekil ve doğru tipte olmalı
assert isinstance(pos, PositionCtx), "pos gölgelendi/yanlış tür: PositionCtx bekleniyor"


# === Binance Client init ===
def initialize_client(retries: int = 3, delay: int = 5) -> Any:
	for attempt in range(1, retries + 1):
		try:
			if _BinanceClient is None:
				raise RuntimeError("binance.client paketi bulunamadı")
			client = _BinanceClient(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
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
def get_current_price(client: Any, symbol: str) -> float | None:
	try:
		ticker = client.get_symbol_ticker(symbol=symbol)
		return float(ticker['price'])
	except Exception as e:
		logger.error(f"Fiyat alınamadı ({symbol}): {e}")
		return None


def get_symbol_filters(client: Any, symbol: str) -> Dict[str, Any]:
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


def quantize_qty_price(client: Any, symbol: str, qty: float, price: float) -> Tuple[float, float]:
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
def analyze_coin_opportunity(client: Any, symbol: str) -> Tuple[float, Dict[str, float]]:
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


def get_volatility_and_volume(client: Any, symbol: str) -> Tuple[float, float, float, float]:
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
	global pos
	print("Project Silent Core v2.3 Başladı")
	print(f"Başlangıç Sermayesi: {BAŞLANGIÇ_SERMEYESİ} USDT")
	print(f"Çalışma Modu: Binance SPOT | EXECUTION_MODE={EXECUTION_MODE} | TESTNET={TESTNET_MODE}")
	print(f"İşlem Yapılacak Coinler: {', '.join(TRADE_SYMBOL_LIST)}")
	print("-" * 42)

	# İki ayrı client: market (live public) + exec (testnet/live)
	# Market verileri için canlı endpoint (daha sağlıklı klines/hacim), emir için mevcut moda göre client
	try:
		if _BinanceClient is None:
			raise RuntimeError("binance.client paketi yok")
		market_client = _BinanceClient()
		market_client.API_URL = 'https://api.binance.com/api'  # live public
	except Exception as e:
		logger.warning(f"Live market client init failed, fallback to exec client for data: {e}")
		market_client = None

	exec_client = initialize_client()

	# Strateji optimizasyonu (opsiyonel)
	try:
		optimize_strategy_parameters()
	except Exception as e:
		logger.warning(f"Strategy optimization failed: {e}")

	# Simülasyon muhasebesi (yaklaşık equity akışı)
	simule_bakiye = float(BAŞLANGIÇ_SERMEYESİ)

	# Risk yöneticisi + yürütücü
	risk_manager = RiskManager(day_start_equity_usdt=simule_bakiye)
	order_executor = OrderExecutor(exec_client, risk_manager=risk_manager)

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
		}
		for coin in TRADE_SYMBOL_LIST
	}

	# İstatistikler
	total_trades = 0
	successful_trades = 0
	total_profit = 0.0
	daily_profit = 0.0
	protection_mode = False

	# Playbook durumu
	trading_enabled = True
	last_refresh = datetime.now()
	candidates = TRADE_SYMBOL_LIST[:]

	while True:
		try:
			# --- Equity'yi güncelle (rapor için) ---
			reporter.set_equity(simule_bakiye)

			# === Günlük hedef/zarar kontrolü ===
			equity = simule_bakiye
			if reporter.start_equity > 0:
				daily_pnl_pct = (equity - reporter.start_equity) / reporter.start_equity * 100
			else:
				daily_pnl_pct = 0.0
			if daily_pnl_pct >= float(_os.getenv("DAILY_TARGET_PCT", 3.13)):
				logger.info("DAILY TARGET REACHED | pct=%s | detail=%s", f"{daily_pnl_pct:.2f}%", "Gün kilitlendi")
				trading_enabled = False
				time.sleep(5)
				continue
			if daily_pnl_pct <= -float(_os.getenv("DAILY_MAX_LOSS_PCT", 1.0)):
				logger.info("DAILY LOSS LIMIT HIT | pct=%s | detail=%s", f"{daily_pnl_pct:.2f}%", "Gün kapatıldı")
				trading_enabled = False
				time.sleep(5)
				continue

			# === Günlük işlem sayısı sınırı ===
			if reporter.summary.get("trade_count", 0) >= int(_os.getenv("DAILY_MAX_TRADES", 12)):
				logger.info("TRADE LIMIT | reason=%s", "Maksimum işlem sayısına ulaşıldı")
				time.sleep(5)
				continue

			# === Aday coin yenileme (4 saatte bir) ===
			from datetime import timedelta
			if datetime.now() >= last_refresh + timedelta(minutes=int(_os.getenv("CANDIDATE_REFRESH_MIN", 240))):
				# Basit yer tutucu: mevcut listeden çalışmaya devam.
				# Burada 24h vol>%6 ve spread<SPREAD_MAX_PCT filtresi entegre edilebilir.
				candidates = TRADE_SYMBOL_LIST[:]
				last_refresh = datetime.now()

			# === Dinamik coin skorlama ===
			coin_scores: Dict[str, float] = {}
			coin_details: Dict[str, Dict[str, float]] = {}
			for symbol in candidates:
				score, details = analyze_coin_opportunity(market_client or exec_client, symbol)
				coin_scores[symbol] = score
				coin_details[symbol] = details
			best_coin = max(coin_scores, key=coin_scores.get)
			best_score = coin_scores.get(best_coin, 0.0)
			best_details = coin_details.get(best_coin, {})

			# === Volatilite/hacim filtresi (scanner ile senkron) ===
			volat_1m, volat_5m, vol_1m, vol_5m = get_volatility_and_volume(market_client or exec_client, best_coin)
			MIN_VOL_1M = float(_os.getenv("MIN_VOL_1M", "0.00005"))
			MIN_VOL_5M = float(_os.getenv("MIN_VOL_5M", "0.0008"))
			MIN_VOL_USDT_5M = float(_os.getenv("MIN_VOL_USDT_5M", "30000"))
			if (volat_1m < MIN_VOL_1M) and (volat_5m < MIN_VOL_5M) and (vol_5m < MIN_VOL_USDT_5M):
				print(f"{best_coin}: Volatilite/hacim düşük, işlem yok. (1mV: {volat_1m:.4f}, 5mV: {volat_5m:.4f}, 1mH: {vol_1m:.0f}, 5mH: {vol_5m:.0f})")
				time.sleep(random.randint(10, 60))
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
			klines_1m = (market_client or exec_client).get_klines(symbol=best_coin, interval='1m', limit=10)
			closes_1m = [float(k[4]) for k in klines_1m]
			volumes_1m = [float(k[5]) for k in klines_1m]
			candles_1m = [{'open': float(k[1]), 'close': float(k[4])} for k in klines_1m]
			klines_3m = (market_client or exec_client).get_klines(symbol=best_coin, interval='3m', limit=3)
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

			# --- Karar görünürlüğü + kontrollü fallback (log10 + cooldown + pozisyon kilidi + bakiye koruması) ---
			symbol = best_coin
			now_ts = int(time.time())
			in_pos = _in_position.get(symbol, current_position["has_position"]) or current_position["has_position"]
			spread = float(best_details.get("spread", 0.0))
			buy_signal = tech.get("buy", False)
			reversal_signal = tech.get("strong_reversal", False)
			spread_ok = (spread < MAX_SPREAD)
			# Standart sinyal kararı
			should_buy = (buy_signal and (not reversal_signal) and spread_ok)
			# Bakiye koruması
			current_balance = simule_bakiye
			TRADE_USDT_AMOUNT = float(IŞLEM_MIKTARI)
			can_afford = (current_balance - TRADE_USDT_AMOUNT) >= MIN_SAFE_BAL_AFTER_BUY
			# Fallback: skorun log10 normalizasyonu + cooldown
			norm_score = math.log10(max(best_score, 1)) if best_score is not None else 0.0
			last_ts = _last_fallback_buy_ts.get(symbol, 0)
			fallback_cooldown_ok = (now_ts - last_ts) >= FALLBACK_COOLDOWN_SEC
			# ENTRY cooldown'u ayrı takip (pozisyon bazlı)
			entry_cooldown_ok = (time.time() - pos.last_action_ts) >= ENTRY_COOLDOWN_SEC if not pos.in_pos else True
			# Fallback tetik bayrağı
			fallback_triggered = False
			if (not should_buy) and (not in_pos) and spread_ok and (not reversal_signal) and can_afford:
				if norm_score >= FORCE_SCORE_LOG10 and fallback_cooldown_ok:
					# Fallback kararını işaretle (ENTRY aşamasında kullanılacak)
					fallback_triggered = True
					_last_fallback_buy_ts[symbol] = now_ts
					print(f"[decision] Fallback BUY: log10(score)={norm_score:.2f} (>= {FORCE_SCORE_LOG10}) | cooldown_ok={fallback_cooldown_ok}")
			# Açık pozisyonda ekstra BUY engeli
			if in_pos:
				should_buy = False
			decision = "BUY" if should_buy else "WAIT"
			print(f"[decision] {symbol} => {decision} | flags="
				  f"buy_signal={buy_signal}, no_reversal={not reversal_signal}, "
				  f"spread_ok={spread_ok}, in_pos={in_pos}, can_afford={can_afford}, "
			      f"log10(score)={norm_score:.2f}, cooldown_ok={fallback_cooldown_ok}")
			if decision == "BUY" and final_decision != "SELL":
				final_decision = "BUY"

			işlem_sonucu = "WAIT ⏸️"
			executed = False
			current_price = get_current_price(market_client or exec_client, best_coin)

			# === Rejim filtresi (15m) ===
			try:
				klines_15m = (market_client or exec_client).get_klines(symbol=best_coin, interval='15m', limit=100)
				ohlcv_15m = [(float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in klines_15m]
			except Exception:
				ohlcv_15m = []
			trend_on = playbook.regime_on(ohlcv_15m) if ohlcv_15m else False
			if not trend_on:
				logger.info("REGIME OFF | symbol=%s | msg=%s", best_coin, "Trend kapalı, scalp mod")

			# === Giriş sinyalleri (1m) ===
			try:
				klines_1m_full = (market_client or exec_client).get_klines(symbol=best_coin, interval='1m', limit=200)
				ohlcv_1m = [(float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in klines_1m_full]
			except Exception:
				ohlcv_1m = []
			signal_breakout = playbook.bb_squeeze_breakout_signal(ohlcv_1m) if ohlcv_1m else False
			signal_pullback = playbook.pullback_signal(ohlcv_1m) if ohlcv_1m else False

			# Orderbook dengesizliği
			try:
				orderbook = (market_client or exec_client).get_order_book(symbol=best_coin, limit=20)
			except Exception:
				orderbook = {"bids": [], "asks": []}
			orderbook_ok = playbook.orderbook_imbalance_ok(orderbook, min_ratio=ORDERBOOK_MIN_RATIO)

			# False-break gecikmesi
			if (signal_breakout or signal_pullback) and orderbook_ok:
				humanizer.random_sleep(
					float(_os.getenv("ORDER_SEND_DELAY_MIN_S", 0.4)),
					float(_os.getenv("ORDER_SEND_DELAY_MAX_S", 2.1))
				)

			# === ENTRY (ALIM) KARARI (WAIT'i kır; trend OFF'ta micro-entry ile al; fallback BUY ile override) ===
			if trading_enabled and not pos.in_pos:
				try:
					vwap_values = [ (float(x[1]) + float(x[4])) / 2.0 for x in (ohlcv_1m or [])][-3:]
				except Exception:
					vwap_values = []
				try:
					volatility_1m = abs((ohlcv_1m[-1][4] - ohlcv_1m[-2][4]) / ohlcv_1m[-2][4]) if (ohlcv_1m and len(ohlcv_1m) >= 2 and ohlcv_1m[-2][4] != 0) else 0.0
				except Exception:
					volatility_1m = 0.0

				long_setup = bool(trend_on and orderbook_ok and (signal_breakout or signal_pullback))
				scalp_setup = bool(SCALP_MODE_ENABLED and (not trend_on) and MICRO_ENTRY_ENABLED and micro_entry_signal(
					ohlcv_1m=ohlcv_1m, vwap=vwap_values, volatility=volatility_1m
				))
				# Normal strateji giriş koşulu
				should_enter = bool(long_setup or scalp_setup)
				# Fallback BUY tetiklendiyse ve izin verildiyse, girişe dahil et
				if FALLBACK_EXECUTE and fallback_triggered and spread_ok and (not reversal_signal) and can_afford:
					should_enter = True

				# ENTRY cooldown'u kullan (fallback cooldown değil)
				if should_enter and entry_cooldown_ok:
					equity = simule_bakiye
					stop_price, qty_base = playbook.compute_stop_and_size(
						entry_price=current_price, ohlcv_1m=ohlcv_1m, equity=equity, risk_pct=RISK_PCT
					)
					qty_base = order_filters.ensure_min_qty(best_coin, float(current_price), float(qty_base or 0.0), MIN_NOTIONAL_USDT)
					qty_base = order_filters.adjust_qty_for_filters(best_coin, qty_base)
					if qty_base and qty_base > 0:
						try:
							# MARKET BUY
							humanizer.humanized_order_wrapper(
								order_executor.execute_order,
								symbol=best_coin,
								side="BUY",
								qty=qty_base,
								price=None
							)

							# POS MUTATION (rebind yok)
							pos.in_pos = True
							pos.symbol = best_coin
							pos.entry_price = float(current_price)
							pos.qty = float(qty_base)
							pos.stop_price = float(stop_price) if stop_price else None
							pos.entry_ts = time.time()
							pos.last_action_ts = time.time()

							logger.info(
								"ENTRY | %s",
								f"BUY {best_coin} qty={qty_base} @ {current_price:.6f} stop={pos.stop_price} | setup={'LONG' if long_setup else 'SCALP'}"
							)

						except Exception as e:
							logger.error(f"Emir gönderilemedi (BUY {best_coin}): {e}")

						# ENTRY bloğunun sonunda daima döngü turunu kapat
						continue
					else:
						logger.info(
							"SIZE-FAIL | %s",
							f"{best_coin} qty=0 | price={current_price} min_notional={MIN_NOTIONAL_USDT} risk_pct={RISK_PCT}"
						)

			# WAIT reason debug
			if not should_enter:
				reasons = []
				if not trend_on: reasons.append("trend_off")
				if not orderbook_ok: reasons.append("lob_fail")
				if not (signal_breakout or signal_pullback): reasons.append("no_brk_pb")
				if trend_on is False and not scalp_setup: reasons.append("no_micro")
				# Entry cooldown engeli
				try:
					if not entry_cooldown_ok: reasons.append("cooldown")
				except Exception:
					pass
				if pos.in_pos: reasons.append("in_pos")
				logger.info("WAIT-REASON | symbol=%s | msg=%s", best_coin, ",".join(reasons) or "none")

			# === EXIT (SATIŞ) KARARI — İLK KÂR FIRSATINDA ÇIKIŞ ===
			if pos.in_pos and pos.symbol == best_coin and current_price:
				now_f = time.time()
				hold_sec = int(now_f - (pos.entry_ts or now_f))
				mark = float(current_price)
				upnl_pct = (mark - pos.entry_price) / pos.entry_price if pos.entry_price else 0.0

				# Sert stop
				if HARD_STOP_LOSS_PCT and upnl_pct <= -HARD_STOP_LOSS_PCT:
					if EXECUTION_MODE == "LIVE":
						order_executor.client = exec_client
					humanizer.humanized_order_wrapper(
						order_executor.execute_order, symbol=best_coin, side="SELL", qty=pos.qty, price=None
					)
					logger.info("EXIT | %s", f"HARD STOP SELL {best_coin} upnl={upnl_pct*100:.2f}% @ {mark:.6f}")
					reset_pos(); continue

				exit_sig = safe_exit_signal(candles_1m=ohlcv_1m, rsi_values=rsi_values, ema_9=ema_9, ema_21=ema_21)

			elif final_decision == "SELL" and current_price and current_position["has_position"]:
				qty_pos = current_position["quantity"]
				qty, price_q = quantize_qty_price(exec_client, best_coin, qty_pos, current_price)
				if qty <= 0:
					print(f"{best_coin}: Miktar 0, SELL atlandı.")
				else:
					fee = 0.0
					if EXECUTION_MODE == "LIVE":
						try:
							order_executor.client = exec_client
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
								if remaining_qty <= 1e-12:
									_in_position[best_coin] = False
								portfolio[best_coin]["trade_count"] = portfolio[best_coin].get("trade_count", 0) + 1
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
						if remaining_qty <= 1e-12:
							_in_position[best_coin] = False
						portfolio[best_coin]["trade_count"] = portfolio[best_coin].get("trade_count", 0) + 1

					# Raporla
					if executed:
						reporter.log_trade(
							symbol=best_coin, side="SELL", qty=qty, price=fill_price, fee_usdt=fee,
							notional_usdt=qty * fill_price, profit_usdt=profit, success=(profit > 0),
						)

			# Stop-loss / Take-profit (yalnızca pozisyon varken)
			if current_position["has_position"]:
				avg_buy = current_position["avg_buy_price"]
				if avg_buy and current_price:
					stop_loss_price = avg_buy * (1 - float(STOP_LOSS_RATIO))
					take_profit_price = avg_buy * (1 + float(TAKE_PROFIT_RATIO))
					if current_price <= stop_loss_price or current_price >= take_profit_price:
						qty = current_position["quantity"]
						qty, _ = quantize_qty_price(exec_client, best_coin, qty, current_price)
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
							_in_position[best_coin] = False
							portfolio[best_coin]["trade_count"] = portfolio[best_coin].get("trade_count", 0) + 1
							# Raporla
							reporter.log_trade(
								symbol=best_coin, side="SELL", qty=qty, price=fill_price, fee_usdt=fee,
								notional_usdt=qty * fill_price, profit_usdt=profit, success=(profit > 0),
							)

			# ENTRY sonrası kısa yeniden-alım cooldown'ı
			cooldown_ok = (time.time() - pos.last_action_ts) >= ENTRY_COOLDOWN_SEC if not pos.in_pos else True

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
			pos_state = 'VAR' if current_position['has_position'] else 'YOK'
			print(f"Pozisyon Durumu: {pos_state}")
			print(f"Trade Kararı: {final_decision}")
			print(f"Karar Sebebi: {('Çıkış koşulları henüz oluşmadı' if pos.in_pos else decision_reason)}")
			print(f"İşlem Sonucu: {işlem_sonucu}")
			print(f"Son İşlem Zamanı: {datetime.now():%Y-%m-%d %H:%M}")
			print(f"Toplam Kâr: {total_profit:+.2f} USDT ({(total_profit/BAŞLANGIÇ_SERMEYESİ)*100:+.1f}%)")
			print(f"Bugünkü Kâr: {daily_profit:+.2f} USDT")
			print(f"Bugün Alım/Satım: {reporter.summary['buy_count']}/{reporter.summary['sell_count']} | Başarılı İşlem: {reporter.summary['success_trades']}")
			print("-" * 42)

			# WAIT sebebi görünürlük
			try:
				reason = []
				if pos.in_pos: reason.append("in_pos")
				if not trend_on: reason.append("trend_off")
				if not orderbook_ok: reason.append("lob_fail")
				if not (signal_breakout or signal_pullback): reason.append("no_brk_pb")
				if MICRO_ENTRY_ENABLED:
					me = micro_entry_signal(ohlcv_1m=ohlcv_1m, vwap=vwap_values if 'vwap_values' in locals() else [], volatility=volatility_1m if 'volatility_1m' in locals() else 0.0)
					if not me: reason.append("no_micro")
				reason_str = ",".join(reason) or "unknown"
				logger.info("WAIT-REASON | %s", f"{best_coin} → {reason_str}")
			except Exception:
				pass

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
			logger.critical("Engine crashed: %s\n%s", e, traceback.format_exc())
			if NOTIFIER_ENABLED:
				try:
					send_notification(f"🚨 BOT HATASI: {e}")
				except Exception:
					pass
			time.sleep(3)
			continue


if __name__ == "__main__":
	main()

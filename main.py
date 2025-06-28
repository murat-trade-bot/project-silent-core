from datetime import datetime
import time
from dotenv import load_dotenv
load_dotenv()
from binance.client import Client
from notifier import send_notification
from config import BAŞLANGIÇ_SERMEYESİ, IŞLEM_MIKTARI, TRADE_INTERVAL, MIN_BAKIYE
from core.logger import BotLogger
from core.engine import BotEngine
from modules.strategy_optimizer import optimize_strategy_parameters
from onchain_alternative import get_trade_signal
import sys

logger = BotLogger()

TRADE_SYMBOL = "BTCUSDT"     # İşlem yapılan coin

TRADE_SYMBOL_LIST = [
    "RVNUSDT", "MASKUSDT", "PEPEUSDT", "ADAUSDT", "SOLUSDT",
    "XRPUSDT", "DOGEUSDT", "TRXUSDT", "SUIUSDT", "HYPEUSDT"
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
    "SUIUSDT": "sui",
    "HYPEUSDT": "hyperliquid"
}

def initialize_client(retries: int = 3, delay: int = 5) -> Client:
    """
    Binance Client'ı tekrar deneyerek başlatır, başarısız olursa bildirir ve çıkar.
    """
    for attempt in range(1, retries + 1):
        try:
            client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
            if getattr(settings, "TESTNET_MODE", False):
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
                if getattr(settings, "NOTIFIER_ENABLED", False):
                    send_notification(f"[CRITICAL] {err_msg}")
                sys.exit(1)

def get_balance(client):
    # Gerçek bakiye çekme kodunu kendi API wrapper'ına göre düzenle
    try:
        balance = client.get_asset_balance(asset='USDT')
        return float(balance['free'])
    except Exception as e:
        logger.error(f"Bakiye çekilemedi: {e}")
        return None

def get_current_price(client, symbol):
    """Coin'in güncel fiyatını al"""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        logger.error(f"Fiyat alınamadı ({symbol}): {e}")
        return None

MAX_RETRIES = 3
RETRY_DELAY = 2  # saniye

class RateLimitError(Exception):
    pass

def safe_get_trade_signal(symbol, coin_id):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_trade_signal(symbol, coin_id)
        except Exception as e:
            # 429 veya rate limit hatası yakalama
            if hasattr(e, "response") and getattr(e.response, "status_code", None) == 429:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    logger.warning(f"Twitter rate limit aşıldı, sinyal atlanıyor: {symbol}")
                    return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
            elif "429" in str(e) or "Too Many Requests" in str(e):
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                else:
                    logger.warning(f"Twitter rate limit aşıldı, sinyal atlanıyor: {symbol}")
                    return {"trade_signal": "WAIT", "whale_score": 0, "twitter_sentiment": 0, "price_trend": 0}
            else:
                logger.error(f"Sinyal alınırken hata: {e}")
                return None

def main():
    print("Project Silent Core v2.1 Başladı")
    print(f"Başlangıç Sermayesi: {BAŞLANGIÇ_SERMEYESİ} USDT")
    print("Çalışma Modu: Binance SPOT")
    print(f"İşlem Yapılacak Coinler: {', '.join(TRADE_SYMBOL_LIST)}")
    print("-" * 30)

    simule_bakiye = BAŞLANGIÇ_SERMEYESİ

    # === POZİSYON TAKİP SİSTEMİ ===
    portfolio = {}
    for coin in TRADE_SYMBOL_LIST:
        portfolio[coin] = {
            "quantity": 0.0,
            "avg_buy_price": 0.0,
            "total_invested": 0.0,
            "has_position": False,
            "last_action": None,
            "trade_count": 0
        }

    # === GENEL İSTATİSTİKLER ===
    total_trades = 0
    successful_trades = 0
    total_profit = 0.0
    daily_profit = 0.0

    # --- DÖNGÜ DIŞINDA CLIENT VE OPTİMİZASYON ---
    client = initialize_client()
    try:
        optimize_strategy_parameters()
    except Exception as e:
        logger.warning(f"Strategy optimization failed: {e}")

    # --- SÜREKLİ ÇALIŞAN ANA DÖNGÜ ---
    daily_profit_reset_flag = False
    while True:
        for TRADE_SYMBOL in TRADE_SYMBOL_LIST:
            # engine = BotEngine(client)  # <-- KALDIRILDI
            current_position = portfolio[TRADE_SYMBOL]
            try:
                analysis_result = safe_get_trade_signal(TRADE_SYMBOL, COIN_ID_MAP.get(TRADE_SYMBOL, "bitcoin"))
                if analysis_result:
                    whale_score = analysis_result.get("whale_score", 0)
                    twitter_sentiment = analysis_result.get("twitter_sentiment", 0)
                    price_trend = analysis_result.get("price_trend", 0)
                    raw_signal = analysis_result.get("trade_signal", "WAIT")

                    final_decision = "WAIT"
                    decision_reason = ""

                    if raw_signal == "BUY":
                        if not current_position["has_position"] and simule_bakiye >= IŞLEM_MIKTARI:
                            final_decision = "BUY"
                            decision_reason = "Sinyal BUY, pozisyon yok, bakiye yeterli"
                        elif current_position["has_position"]:
                            final_decision = "WAIT"
                            decision_reason = "Sinyal BUY ama zaten pozisyon var"
                        else:
                            final_decision = "WAIT"
                            decision_reason = "Sinyal BUY ama bakiye yetersiz"

                    elif raw_signal == "SELL":
                        if current_position["has_position"]:
                            final_decision = "SELL"
                            decision_reason = "Sinyal SELL, pozisyon var"
                        else:
                            final_decision = "WAIT"
                            decision_reason = "Sinyal SELL ama pozisyon yok"
                    else:
                        final_decision = "WAIT"
                        decision_reason = "Analiz sonucu WAIT"

                    if final_decision == "BUY":
                        current_price = get_current_price(client, TRADE_SYMBOL)
                        if current_price:
                            quantity = IŞLEM_MIKTARI / current_price
                            simule_bakiye -= IŞLEM_MIKTARI
                            # In-place güncelleme
                            current_position["quantity"] = quantity
                            current_position["avg_buy_price"] = current_price
                            current_position["total_invested"] = IŞLEM_MIKTARI
                            current_position["has_position"] = True
                            current_position["last_action"] = "BUY"
                            current_position["trade_count"] += 1
                            işlem_sonucu = "BUY Executed ✅"
                    elif final_decision == "SELL":
                        current_price = get_current_price(client, TRADE_SYMBOL)
                        if current_price:
                            sell_amount = current_position["quantity"] * current_price
                            profit = sell_amount - current_position["total_invested"]
                            simule_bakiye += sell_amount
                            total_profit += profit
                            daily_profit += profit
                            if profit > 0:
                                successful_trades += 1
                            # In-place güncelleme
                            current_position["quantity"] = 0.0
                            current_position["avg_buy_price"] = 0.0
                            current_position["total_invested"] = 0.0
                            current_position["has_position"] = False
                            current_position["last_action"] = "SELL"
                            current_position["trade_count"] += 1
                            işlem_sonucu = f"SELL Executed ✅ (Profit: {profit:.2f} USDT)"
                    else:
                        işlem_sonucu = "WAIT ⏸️"

                    total_trades += 1

                    # Tek satırlık özet log formatı
                    log_msg = (
                        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                        f"{TRADE_SYMBOL:<8} | Karar: {final_decision:<4} | "
                        f"Bakiye: {simule_bakiye:8.2f} USDT | "
                        f"Toplam Kâr: {total_profit:+7.2f} ({(total_profit/BAŞLANGIÇ_SERMEYESİ)*100:+5.1f}%) | "
                        f"İşlem Sayısı: {current_position['trade_count']}"
                    )
                    print(log_msg)

                    if simule_bakiye < MIN_BAKIYE:
                        print(f"Bakiye {MIN_BAKIYE} USDT altına düştü, işlem durduruldu.")
                        return

                    time.sleep(TRADE_INTERVAL)
        # Her gün saat 00:00'da günlük kârı sadece bir kez sıfırla
        now = datetime.now()
        if now.hour == 0 and now.minute == 0 and not daily_profit_reset_flag:
            daily_profit = 0.0
            logger.info("Günlük kâr resetlendi.")
            daily_profit_reset_flag = True
        elif now.hour != 0:
            daily_profit_reset_flag = False

if __name__ == "__main__":
    main()

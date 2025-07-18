from datetime import datetime
import time
from dotenv import load_dotenv
load_dotenv()
from binance.client import Client
from notifier import send_notification
from config import settings
from config import BAŞLANGIÇ_SERMEYESİ, IŞLEM_MIKTARI, TRADE_INTERVAL, MIN_BAKIYE, STOP_LOSS_RATIO, TAKE_PROFIT_RATIO
from core.logger import BotLogger
from core.engine import BotEngine
from modules.strategy_optimizer import optimize_strategy_parameters
from onchain_alternative import get_trade_signal, run_onchain_alternative
import sys
import random
import json

logger = BotLogger()

TRADE_SYMBOL = "BTCUSDT"     # İşlem yapılan coin

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

def slice_and_execute_buy(client, symbol, total_amount, slices=4, price_variation=0.001):
    """
    Belirtilen tutarı küçük limit emirlerine bölerek rastgele fiyat sapması ve zaman jitter ile alım yapar.
    slices: parça sayısı
    price_variation: limit fiyat sapması oranı
    """
    slice_amount = total_amount / slices
    for i in range(slices):
        # Mevcut fiyatı al
        market_price = get_current_price(client, symbol)
        if not market_price:
            continue
        # Limit fiyatını aşağı doğru rastgele sapma ile belirle
        limit_price = round(market_price * (1 - random.uniform(0, price_variation)), 6)
        try:
            client.order_limit_buy(symbol=symbol, quantity=round(slice_amount/limit_price, 6), price=str(limit_price))
        except Exception as e:
            logger.error(f"Slice buy emri başarısız ({symbol}): {e}")
        # Rastgele jitter
        time.sleep(random.uniform(1, 3))

def analyze_coin_opportunity(client, symbol):
    """
    Coin için volatilite, hacim ve spread skorunu hesaplar.
    Dönüş: skor (float), detay dict
    """
    try:
        # Fiyat volatilitesi (son 5 dakika)
        klines = client.get_klines(symbol=symbol, interval='1m', limit=5)
        close_prices = [float(k[4]) for k in klines]
        if len(close_prices) < 2:
            return 0, {}
        volatility = (max(close_prices) - min(close_prices)) / close_prices[0]

        # 24s hacim
        ticker = client.get_ticker(symbol=symbol)
        volume = float(ticker.get('quoteVolume', 0))

        # Spread (alış-satış farkı)
        order_book = client.get_order_book(symbol=symbol, limit=5)
        bid = float(order_book['bids'][0][0])
        ask = float(order_book['asks'][0][0])
        spread = (ask - bid) / bid if bid > 0 else 0

        # Skor: volatilite * hacim / (spread + 0.0001) (spread küçükse skor artar)
        score = volatility * volume / (spread + 0.0001)
        details = {
            "volatility": volatility,
            "volume": volume,
            "spread": spread,
            "score": score
        }
        return score, details
    except Exception as e:
        logger.warning(f"{symbol} için fırsat analizi yapılamadı: {e}")
        return 0, {}

# --- Volatilite ve hacim eşikleri ---
VOLATILITY_THRESHOLD_1M = 0.001  # %0.1
VOLATILITY_THRESHOLD_5M = 0.002  # %0.2
VOLUME_THRESHOLD_1M = 5000       # 1 dakikalık hacim
VOLUME_THRESHOLD_5M = 20000      # 5 dakikalık hacim
SLIPPAGE_LIMIT = 0.005           # %0.5

def get_volatility_and_volume(client, symbol):
    """Son 1dk ve 5dk volatilite ve hacim hesapla"""
    try:
        klines_1m = client.get_klines(symbol=symbol, interval='1m', limit=5)
        closes = [float(k[4]) for k in klines_1m]
        vols = [float(k[5]) for k in klines_1m]
        if len(closes) < 5:
            return 0, 0, 0, 0
        vol_1m = vols[-1]
        vol_5m = sum(vols)
        volat_1m = abs(closes[-1] - closes[-2]) / closes[-2] if closes[-2] != 0 else 0
        volat_5m = (max(closes) - min(closes)) / closes[0] if closes[0] != 0 else 0
        return volat_1m, volat_5m, vol_1m, vol_5m
    except Exception as e:
        logger.warning(f"{symbol} için volatilite/hacim hesaplanamadı: {e}")
        return 0, 0, 0, 0

def check_slippage(expected_price, actual_price):
    """Slippage oranını hesapla ve limiti aşarsa True döndür"""
    if expected_price == 0:
        return False
    slippage = abs(actual_price - expected_price) / expected_price
    return slippage > SLIPPAGE_LIMIT

def log_daily_report(filename, report):
    """Günlük performans raporunu dosyaya kaydet"""
    try:
        with open(filename, "a") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Günlük rapor kaydedilemedi: {e}")

def main():
    print("Project Silent Core v2.1 Başladı")
    # Kullanılacak coin listesi
    trade_symbols = TRADE_SYMBOL_LIST
    print(f"Başlangıç Sermayesi: {BAŞLANGIÇ_SERMEYESİ} USDT")
    print("Çalışma Modu: Binance SPOT")
    print(f"İşlem Yapılacak Coinler: {', '.join(TRADE_SYMBOL_LIST)}")
    print("-" * 30)

    simule_bakiye = BAŞLANGIÇ_SERMEYESİ
    daily_start_balance = BAŞLANGIÇ_SERMEYESİ

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

    # --- Günlük rapor değişkenini başta tanımla ---
    daily_report = {
        "date": "",
        "total_profit": 0.0,
        "daily_profit": 0.0,
        "trade_count": 0,
        "buy_count": 0,
        "sell_count": 0,
        "coins_traded": [],
        "success_trades": 0
    }

    # --- DÖNGÜ DIŞINDA CLIENT VE OPTİMİZASYON ---
    client = initialize_client()
    try:
        optimize_strategy_parameters()
    except Exception as e:
        logger.warning(f"Strategy optimization failed: {e}")

    daily_profit_reset_flag = False
    protection_mode = False
    emergency_mode = False
    last_trade_price = {}
    daily_report_file = f"daily_report_{datetime.now():%Y%m%d}.log"

    # --- SÜREKLİ ÇALIŞAN ANA DÖNGÜ ---
    while True:
        # --- Dinamik coin fırsat analizi ---
        coin_scores = {}
        coin_details = {}
        for symbol in trade_symbols:
            score, details = analyze_coin_opportunity(client, symbol)
            coin_scores[symbol] = score
            coin_details[symbol] = details
        # En yüksek skorlu coini seç
        best_coin = max(coin_scores, key=coin_scores.get)
        best_score = coin_scores[best_coin]
        best_details = coin_details[best_coin]

        # --- Volatilite ve hacim filtresi ---
        volat_1m, volat_5m, vol_1m, vol_5m = get_volatility_and_volume(client, best_coin)
        if (volat_1m < VOLATILITY_THRESHOLD_1M or volat_5m < VOLATILITY_THRESHOLD_5M or
            vol_1m < VOLUME_THRESHOLD_1M or vol_5m < VOLUME_THRESHOLD_5M):
            print(f"{best_coin}: Volatilite/hacim düşük, işlem yapılmıyor. (1mV: {volat_1m:.4f}, 5mV: {volat_5m:.4f}, 1mH: {vol_1m:.0f}, 5mH: {vol_5m:.0f})")
            time.sleep(random.randint(10, 60))
            continue

        # --- Günlük kâr bariyeri ve koruma ---
        daily_profit_pct = (simule_bakiye - daily_start_balance) / daily_start_balance * 100
        if daily_profit_pct >= 6:
            if not protection_mode:
                print("\n=== Kâr Kilidi Aktif! Günlük %6 hedefe ulaşıldı, işlemler durduruldu. ===")
                logger.info("Kâr kilidi aktif: Günlük %6 kâr hedefi aşıldı, koruma moduna geçildi.")
                send_notification("🔒 Kâr kilidi aktif! Günlük %6 ulaşıldı, işlemler durduruldu.")
                protection_mode = True
        if protection_mode:
            print(f"{best_coin}: Kâr kilidi aktif, işlem yapılmıyor.")
            time.sleep(random.randint(10, 60))
            continue

        # --- Acil durum koruma (slippage, ani düşüş) ---
        if emergency_mode:
            print("Acil durum koruma modu aktif! Tüm işlemler durduruldu.")
            send_notification("🚨 Acil durum: Bot işlemleri durdurdu!")
            break

        TRADE_SYMBOL = best_coin
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
                # --- Emir miktarına rastgele varyasyon ekle ---
                miktar_varyasyon = random.uniform(0.9, 1.1)  # %10 varyasyon
                işlem_miktarı = IŞLEM_MIKTARI * miktar_varyasyon
                if raw_signal == "BUY":
                    if not current_position["has_position"] and simule_bakiye >= işlem_miktarı:
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
                # Stop-loss/take-profit zorunlu satış yok, sadece sinyale göre işlem yapılır

                işlem_sonucu = "WAIT ⏸️"
                executed = False
                if final_decision == "BUY":
                    current_price = get_current_price(client, TRADE_SYMBOL)
                    if current_price:
                        # Slippage kontrolü (alımda)
                        if TRADE_SYMBOL in last_trade_price and check_slippage(last_trade_price[TRADE_SYMBOL], current_price):
                            print(f"{TRADE_SYMBOL}: Slippage limiti aşıldı! Acil durum koruma devreye giriyor.")
                            emergency_mode = True
                            continue
                        quantity = işlem_miktarı / current_price
                        simule_bakiye -= işlem_miktarı
                        current_position["quantity"] = quantity
                        current_position["avg_buy_price"] = current_price
                        current_position["total_invested"] = işlem_miktarı
                        current_position["has_position"] = True
                        current_position["last_action"] = "BUY"
                        current_position["trade_count"] += 1
                        işlem_sonucu = "BUY Executed ✅"
                        executed = True
                        last_trade_price[TRADE_SYMBOL] = current_price
                        daily_report["buy_count"] += 1
                elif final_decision == "SELL":
                    current_price = get_current_price(client, TRADE_SYMBOL)
                    if current_price:
                        # Slippage kontrolü (satışta)
                        if TRADE_SYMBOL in last_trade_price and check_slippage(last_trade_price[TRADE_SYMBOL], current_price):
                            print(f"{TRADE_SYMBOL}: Slippage limiti aşıldı! Acil durum koruma devreye giriyor.")
                            emergency_mode = True
                            continue
                        sell_amount = current_position["quantity"] * current_price
                        profit = sell_amount - current_position["total_invested"]
                        simule_bakiye += sell_amount
                        total_profit += profit
                        daily_profit += profit
                        if profit > 0:
                            successful_trades += 1
                            daily_report["success_trades"] += 1
                        current_position["quantity"] = 0.0
                        current_position["avg_buy_price"] = 0.0
                        current_position["total_invested"] = 0.0
                        current_position["has_position"] = False
                        current_position["last_action"] = "SELL"
                        current_position["trade_count"] += 1
                        işlem_sonucu = f"SELL Executed ✅ (Profit: {profit:.2f} USDT)"
                        executed = True
                        last_trade_price[TRADE_SYMBOL] = current_price
                        daily_report["sell_count"] += 1

                total_trades += 1
                daily_report["trade_count"] += 1
                if executed:
                    # .add() yerine .append() kullanılmalı, çünkü başta liste olarak tanımlı
                    if TRADE_SYMBOL not in daily_report["coins_traded"]:
                        daily_report["coins_traded"].append(TRADE_SYMBOL)

                # Tek satırlık özet log formatı
                daily_cum_profit_pct = (simule_bakiye - daily_start_balance) / daily_start_balance * 100
                log_msg = (
                    f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                    f"{TRADE_SYMBOL:<8} | Karar: {final_decision:<4} | "
                    f"Bakiye: {simule_bakiye:8.2f} USDT | "
                    f"Toplam Kâr: {total_profit:+7.2f} ({(total_profit/BAŞLANGIÇ_SERMEYESİ)*100:+5.1f}%) | "
                    f"Günlük Kümülatif Kâr: {daily_cum_profit_pct:+5.2f}% | "
                    f"İşlem Sayısı: {current_position['trade_count']}"
                )
                print(log_msg)
                # Hedeflenen detaylı format
                # Onchain Alternative hata veya bilgi mesajları işlenmiş olsun
                # RSI, whale_score vs. loglandı
                onchain_data = analysis_result.get('onchain_data', {})
                ws = onchain_data.get('whale_score', 0)
                ts = onchain_data.get('twitter_sentiment', 0)
                pt = onchain_data.get('price_trend', 0)
                print(f"whale_score: {ws}, twitter_sentiment: {ts}, price_trend: {pt}")
                print(f"Fırsat Skoru: {best_score:.4f} | Volatilite: {best_details.get('volatility',0):.4f} | Hacim: {best_details.get('volume',0):.2f} | Spread: {best_details.get('spread',0):.6f}")
                print(f"Güncel Bakiye: {simule_bakiye:.2f} USDT")
                print(f"Trade Döngüsü: {total_trades}")
                print(f"İşlem Yapılan Coin: {TRADE_SYMBOL}")
                pos = 'VAR' if current_position['has_position'] else 'YOK'
                print(f"Pozisyon Durumu: {pos}")
                print(f"Trade Kararı: {final_decision}")
                print(f"Karar Sebebi: {decision_reason}")
                print(f"İşlem Sonucu: {işlem_sonucu}")
                print(f"Son İşlem Zamanı: {datetime.now():%Y-%m-%d %H:%M}")
                print(f"Güncel Bakiye: {simule_bakiye:.2f} USDT")
                print(f"Toplam Kâr: {total_profit:+.2f} USDT ({(total_profit/BAŞLANGIÇ_SERMEYESİ)*100:+.1f}%)")
                print(f"Bugünkü Kâr: {daily_profit:+.2f} USDT")
                rate = successful_trades/total_trades*100 if total_trades>0 else 0
                print(f"Başarılı İşlem Oranı: {rate:.1f}% ({successful_trades}/{total_trades})")
                print("-"*30)

                if simule_bakiye < MIN_BAKIYE:
                    print(f"Bakiye {MIN_BAKIYE} USDT altına düştü, işlem durduruldu.")
                    break

                rastgele_aralik = random.randint(10, 60)
                time.sleep(rastgele_aralik)
        except Exception as e:
            logger.critical(f"Engine crashed: {e}")
            send_notification(f"🚨 BOT HATASI: {e}")

        # --- Gün sonu raporlama ve reset ---
        now = datetime.now()
        if now.hour == 0 and now.minute == 0 and not daily_profit_reset_flag:
            daily_report["date"] = now.strftime("%Y-%m-%d")
            daily_report["total_profit"] = total_profit
            daily_report["daily_profit"] = daily_profit
            # set yerine liste kullan
            if isinstance(daily_report["coins_traded"], set):
                daily_report["coins_traded"] = list(daily_report["coins_traded"])
            log_daily_report(daily_report_file, daily_report)
            print(f"\n--- Gün Sonu Raporu ---\nGünlük Kümülatif Kâr: {(simule_bakiye - daily_start_balance) / daily_start_balance * 100:+.2f}%\nGünlük Kâr: {daily_profit:+.2f} USDT\nToplam İşlem: {daily_report['trade_count']}\nAlım: {daily_report['buy_count']} | Satım: {daily_report['sell_count']}\nBaşarılı İşlem: {daily_report['success_trades']}\nİşlem Yapılan Coinler: {', '.join(daily_report['coins_traded'])}\n----------------------\n")
            daily_profit = 0.0
            daily_start_balance = simule_bakiye
            protection_mode = False
            logger.info("Günlük kâr ve kümülatif oran resetlendi, koruma modu kapatıldı.")
            daily_profit_reset_flag = True
            # Günlük rapor sıfırla
            daily_report = {
                "date": "",
                "total_profit": 0.0,
                "daily_profit": 0.0,
                "trade_count": 0,
                "buy_count": 0,
                "sell_count": 0,
                "coins_traded": [],
                "success_trades": 0
            }
        elif now.hour != 0:
            daily_profit_reset_flag = False

if __name__ == "__main__":
    main()

import csv
import os
import time
import traceback
import math
import random

from config import settings
from core.logger import BotLogger
from security.stealth_mode import stealth

logger = BotLogger()

try:
    from binance.client import Client
    BINANCE_INSTALLED = True
except ImportError:
    BINANCE_INSTALLED = False
    logger.log("[WARN] python-binance kurulu değil, gerçek emir olmayacak.")

class ExecutorManager:
    def __init__(self):
        if settings.PAPER_TRADING:
            self.executor = PaperTradeExecutor()
        else:
            if BINANCE_INSTALLED:
                self.executor = BinanceOCOExecutor()
            else:
                self.executor = PaperTradeExecutor()

    def manage_position(self, action):
        try:
            if action == "HOLD":
                logger.log("[EXEC] HOLD => emir yok.")
                return
            self.executor.execute_trade(action)
        except Exception as e:
            logger.log(f"[EXEC] Emir hata: {e}")
            logger.log(traceback.format_exc())

class PaperTradeExecutor:
    def __init__(self):
        self.balance = settings.INITIAL_BALANCE
        self.position = 0.0
        self.avg_price = 0.0
        self.csv_file = settings.CSV_LOG_FILE
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "action", "price", "amount", "balance", "position", "avg_price"])
        self.client = None
        if BINANCE_INSTALLED:
            from binance.client import Client
            self.client = Client("", "")

    def get_mock_price(self):
        symbol = settings.SYMBOL
        if self.client:
            try:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                return float(ticker["price"])
            except:
                pass
        return 28000 + 500 * math.sin(time.time() / 60)

    def execute_trade(self, action):
        mock_price = self.get_mock_price()
        usd_equity = self.balance
        trade_amount_usd = usd_equity * settings.POSITION_SIZE_PCT
        trade_amount_usd = stealth.apply_order_size_jitter(trade_amount_usd)
        amount_btc = trade_amount_usd / mock_price
        timestamp = int(time.time())

        if action == "BUY":
            cost = mock_price * amount_btc
            if cost <= self.balance:
                self.balance -= cost
                total_pos_value = self.position * self.avg_price
                new_total = total_pos_value + cost
                self.position += amount_btc
                if self.position > 0:
                    self.avg_price = new_total / self.position
                logger.log(f"[PAPER] BUY {amount_btc:.6f} BTC @ {mock_price:.2f}, Bakiye={self.balance:.2f}, Pos={self.position:.6f}")
            else:
                logger.log("[PAPER] Yetersiz bakiye, BUY başarısız.")
                return

        elif action == "SELL":
            if self.position > 0:
                if amount_btc > self.position:
                    amount_btc = self.position
                revenue = mock_price * amount_btc
                self.balance += revenue
                self.position -= amount_btc
                logger.log(f"[PAPER] SELL {amount_btc:.6f} BTC @ {mock_price:.2f}, Bakiye={self.balance:.2f}, Pos={self.position:.6f}")
                if self.position < 1e-6:
                    self.position = 0.0
                    self.avg_price = 0.0
            else:
                logger.log("[PAPER] BTC yok, SELL başarısız.")
                return

        with open(self.csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, action, round(mock_price, 2), round(amount_btc, 6),
                             round(self.balance, 2), round(self.position, 6), round(self.avg_price, 2)])

class BinanceOCOExecutor:
    def __init__(self):
        from binance.client import Client
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.symbol = settings.SYMBOL
        self.client = Client(self.api_key, self.api_secret)
        if settings.TESTNET_MODE:
            self.client.API_URL = "https://testnet.binance.vision/api"

    def execute_trade(self, action):
        account_info = self.client.get_account()
        balances = account_info["balances"]
        usdt_balance = 0.0
        btc_balance = 0.0
        for b in balances:
            if b["asset"] == "USDT":
                usdt_balance = float(b["free"])
            elif b["asset"] == "BTC":
                btc_balance = float(b["free"])

        time.sleep(random.uniform(1, 5))
        if action == "BUY":
            trade_amount_usd = usdt_balance * settings.POSITION_SIZE_PCT
            trade_amount_usd = stealth.apply_order_size_jitter(trade_amount_usd)
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            current_price = float(ticker["price"])
            buy_qty = round(trade_amount_usd / current_price, 6)
            if buy_qty < 0.0001:
                logger.log("[BINANCE] Emir boyutu çok küçük, BUY iptal.")
                return
            logger.log(f"[BINANCE] MARKET BUY => {buy_qty} BTC @ {current_price:.2f}")
            buy_order = self.client.create_order(
                symbol=self.symbol,
                side="BUY",
                type="MARKET",
                quantity=buy_qty
            )
            logger.log(f"[BINANCE] BUY order => {buy_order}")
            time.sleep(random.uniform(2, 5))
            fills = buy_order.get("fills", [])
            fill_price = float(fills[0]["price"]) if fills else current_price
            stop_loss_price = round(fill_price * (1 - settings.STOP_LOSS_RATIO), 2)
            take_profit_price = round(fill_price * (1 + settings.TAKE_PROFIT_RATIO), 2)
            oco_qty = round(buy_qty, 6)
            if oco_qty >= 0.0001:
                try:
                    oco_order = self.client.create_oco_order(
                        symbol=self.symbol,
                        side="SELL",
                        quantity=oco_qty,
                        price=str(take_profit_price),
                        stopPrice=str(stop_loss_price),
                        stopLimitPrice=str(round(stop_loss_price * 0.999, 2)),
                        stopLimitTimeInForce="GTC"
                    )
                    logger.log(f"[BINANCE] OCO SELL => {oco_order}")
                except Exception as e:
                    logger.log(f"[BINANCE] OCO SELL hata: {e}")
        elif action == "SELL":
            if btc_balance < 0.0001:
                logger.log("[BINANCE] BTC yok, SELL iptal.")
                return
            sell_qty = round(stealth.apply_order_size_jitter(btc_balance * 0.5), 6)
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            current_price = float(ticker["price"])
            logger.log(f"[BINANCE] MARKET SELL => {sell_qty} BTC @ {current_price:.2f}")
            sell_order = self.client.create_order(
                symbol=self.symbol,
                side="SELL",
                type="MARKET",
                quantity=sell_qty
            )
            logger.log(f"[BINANCE] SELL order => {sell_order}") 
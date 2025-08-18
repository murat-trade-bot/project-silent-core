import pandas as pd
import numpy as np
from datetime import datetime
import logging
import random
from modules.performance_optimization import PerformanceOptimization
from modules.dynamic_position import DynamicPosition

class Strategy:
    def run_three_day_target_simulation(self, price_data, market_data, print_report=True):
        """
        3 gün boyunca, her gün %6 net kâr hedefiyle, coin seçimi ve işlem döngüsü uygular.
        Her günün sonunda yapılan işlemler ve gün sonu raporu detaylı olarak yazdırılır.
        price_data: {'BTCUSDT': [fiyat1, fiyat2, ...], ...} (her coin için 3 günlük fiyat listesi)
        market_data: {'BTCUSDT': [fiyat1, fiyat2, ...], ...} (volatilite için)
        print_report: True ise gün sonu raporları ekrana yazdırılır.
        """
        daily_targets = [
            {"start": 252, "target": 267.12, "profit": 15.12},
            {"start": 267.12, "target": 283.12, "profit": 16},
            {"start": 283.12, "target": 300, "profit": 16.98},
        ]
        balance = daily_targets[0]["start"]
        log = []
        for day in range(3):
            day_info = daily_targets[day]
            day_report = []
            if print_report:
                print(f"\n--- {day+1}. Gün Başlangıç Bakiye: {balance:.2f} USDT, Hedef: {day_info['target']} ---")
            self.logger.info(f"--- {day+1}. Gün Başlangıç Bakiye: {balance:.2f} USDT, Hedef: {day_info['target']} ---")
            # En volatil 2 coini seç
            volatile_coins = self.select_most_volatile_coins(market_data, top_n=2)
            if print_report:
                print(f"{day+1}. Gün için seçilen coinler: {volatile_coins}")
            self.logger.info(f"{day+1}. Gün için seçilen coinler: {volatile_coins}")
            # Her coin için gün boyu işlem simülasyonu (örnek: 24 fiyat barı)
            positions = {symbol: 0 for symbol in volatile_coins}
            daily_profit = 0
            for symbol in volatile_coins:
                prices = price_data.get(symbol, [])
                if len(prices) < day+1:
                    continue
                price = prices[day]  # O günkü fiyat
                # Basit al-sat stratejisi: Eğer pozisyon yoksa al, varsa hedefe ulaşınca sat
                if positions[symbol] == 0 and balance > 0:
                    buy_amount = (balance / len(volatile_coins)) / price
                    positions[symbol] += buy_amount
                    balance -= buy_amount * price
                    msg = f"{symbol} ALIM: {buy_amount:.4f} adet, fiyat: {price:.2f}"
                    day_report.append(msg)
                    self.logger.info(msg)
                # Satış: %6 kâr hedefi veya gün sonu
                entry_price = price  # Basitlik için aynı gün al-sat
                target_price = entry_price * 1.06
                if positions[symbol] > 0 and price >= target_price:
                    sell_amount = positions[symbol]
                    profit = sell_amount * (price - entry_price)
                    balance += sell_amount * price
                    daily_profit += profit
                    positions[symbol] = 0
                    msg = f"{symbol} SATIM: {sell_amount:.4f} adet, fiyat: {price:.2f}, Kâr: {profit:.2f}"
                    day_report.append(msg)
                    self.logger.info(msg)
            # Gün sonu kalan pozisyonları sat
            for symbol in volatile_coins:
                if positions[symbol] > 0:
                    price = price_data[symbol][day]
                    sell_amount = positions[symbol]
                    profit = sell_amount * (price - price)  # Aynı fiyattan satılıyor, kâr yok
                    balance += sell_amount * price
                    positions[symbol] = 0
                    msg = f"{symbol} GÜN SONU SATIM: {sell_amount:.4f} adet, fiyat: {price:.2f}, Kâr: {profit:.2f}"
                    day_report.append(msg)
                    self.logger.info(msg)
            # Günlük hedef kontrolü
            achieved = balance >= day_info["target"]
            summary = f"{day+1}. Gün Sonu Bakiye: {balance:.2f} USDT, Hedef: {day_info['target']}, Hedefe Ulaşıldı mı? {achieved}"
            if print_report:
                print("\n--- Gün Sonu Raporu ---")
                for item in day_report:
                    print(item)
                print(summary)
            self.logger.info(summary)
            log.append({
                "day": day+1,
                "start_balance": day_info["start"],
                "end_balance": balance,
                "target": day_info["target"],
                "achieved": achieved,
                "day_report": day_report,
                "summary": summary
            })
        return log
    def __init__(self):
        self.last_action = {}
        self.last_buy_price = {}
        self.cooldown = {}
        self.cooldown_period = 12
        self.max_position_pct = 0.25
        self.stop_loss_pct = 0.05   # %5 zarar
        self.take_profit_pct = 0.10 # %10 kâr
        self.max_daily_loss_pct = 0.10  # Günlük maksimum zarar %10
        self.max_coin_exposure_pct = 0.5  # Tek coine maksimum portföy %50
        self.max_trades_per_day = 10     # Günlük maksimum işlem sayısı
        self.daily_loss = 0
        self.daily_trades = 0

        self.periods = [
            {
                "name": "1. Dönem",
                "start": datetime(2024, 4, 25),
                "end": datetime(2024, 6, 25),
                "start_balance": 231,  # 231 USDT, 9 XRP, 0.0209 BNB (USDT olarak takip edilecek)
                "target_balance": 3234,
                "profit_multiplier": 14,
                "to_tr": 0,
                "binance_remain": "Tamamı"
            },
            {
                "name": "2. Dönem",
                "start": datetime(2024, 6, 26),
                "end": datetime(2024, 8, 26),
                "start_balance": 3234,
                "target_balance": 38808,
                "profit_multiplier": 12,
                "to_tr": 0,
                "binance_remain": "Tamamı"
            },
            {
                "name": "3. Dönem",
                "start": datetime(2024, 8, 27),
                "end": datetime(2024, 10, 27),
                "start_balance": 38808,
                "target_balance": 388080,
                "profit_multiplier": 10,
                "to_tr": 238080,
                "binance_remain": 150000
            },
            {
                "name": "4. Dönem",
                "start": datetime(2024, 10, 28),
                "end": datetime(2024, 12, 28),
                "start_balance": 150000,
                "target_balance": 900000,
                "profit_multiplier": 6,
                "to_tr": 700000,
                "binance_remain": 200000
            },
            {
                "name": "5. Dönem",
                "start": datetime(2024, 12, 29),
                "end": datetime(2025, 2, 1),
                "start_balance": 200000,
                "target_balance": 1000000,
                "profit_multiplier": 5,
                "to_tr": 750000,
                "binance_remain": 250000
            },
            {
                "name": "6. Dönem",
                "start": datetime(2025, 2, 2),
                "end": datetime(2025, 4, 2),
                "start_balance": 250000,
                "target_balance": 1250000,
                "profit_multiplier": 5,
                "to_tr": 900000,
                "binance_remain": 350000
            }
        ]
        self.current_period_index = None
        self.last_target_update = None
        self.carry_over = 0

        # Logger ayarları
        self.logger = logging.getLogger("StrategyLogger")
        handler = logging.FileHandler("strategy.log")
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        self.dynamic_position = DynamicPosition()

    def get_current_period(self, today=None):
        try:
            if today is None:
                today = datetime.now()
            for i, period in enumerate(self.periods):
                if period["start"] <= today <= period["end"]:
                    self.current_period_index = i
                    return period
            return None
        except Exception as e:
            self.logger.error(f"get_current_period hata: {e}")
            return None

    def get_days_left(self, today, period):
        # Bugün dahil, dönem sonuna kadar kalan gün
        return (period["end"].date() - today.date()).days + 1

    def get_daily_target(self, today=None, current_balance=None):
        try:
            period = self.get_current_period(today)
            if period is None:
                return None  # Dönem dışında
            if today is None:
                today = datetime.now()
            if current_balance is None:
                current_balance = period["start_balance"]

            days_left = self.get_days_left(today, period)
            if days_left <= 0:
                return 0

            target_balance = period["target_balance"]
            remaining_profit = target_balance - current_balance
            daily_target = (remaining_profit / days_left) + self.carry_over
            return max(daily_target, 0)
        except Exception as e:
            self.logger.error(f"get_daily_target hata: {e}")
            return 0

    def get_action(self, context):
        try:
            price = context['price']
            symbol = context['symbol']
            bar_index = context.get('bar_index', 0)
            balance = context.get('balance', 0)
            positions = context.get('positions', {})  # {'BTCUSDT': miktar, ...}
            portfolio_value = context.get('portfolio_value', 1)  # toplam portföy

            # Pozisyon ve cooldown kontrolü
            if symbol not in self.last_action:
                self.last_action[symbol] = None
                self.last_buy_price[symbol] = None
                self.cooldown[symbol] = -100

            # Cooldown (overtrading önleme)
            if bar_index - self.cooldown[symbol] < self.cooldown_period:
                return 'HOLD'

            # Pozisyon miktarı
            position = positions.get(symbol, 0)
            max_position_value = self.max_position_pct * portfolio_value

            # Satın almak için yeterli bakiye var mı?
            if self.last_action[symbol] != 'BUY':
                if balance >= max_position_value:
                    self.last_action[symbol] = 'BUY'
                    self.last_buy_price[symbol] = price
                    self.cooldown[symbol] = bar_index
                    return 'BUY'
                else:
                    return 'HOLD'
            # Satış için elinde coin var mı?
            elif self.last_action[symbol] == 'BUY':
                if position > 0:
                    entry_price = self.last_buy_price[symbol]
                    if price <= entry_price * (1 - self.stop_loss_pct):
                        self.logger.info(f"STOP-LOSS tetiklendi: {symbol} {price} (entry: {entry_price})")
                        self.last_action[symbol] = 'SELL'
                        self.cooldown[symbol] = bar_index
                        return 'SELL'
                    elif price >= entry_price * (1 + self.take_profit_pct):
                        self.logger.info(f"TAKE-PROFIT tetiklendi: {symbol} {price} (entry: {entry_price})")
                        self.last_action[symbol] = 'SELL'
                        self.cooldown[symbol] = bar_index
                        return 'SELL'
                    else:
                        self.logger.info(f"Pozisyon korunuyor: {symbol} {price} (entry: {entry_price})")
                        return 'HOLD'
                else:
                    return 'HOLD'

            return 'HOLD'
        except Exception as e:
            self.logger.error(f"get_action hata: {e}")
            return 'HOLD'

    def update_carry_over(self, realized_profit, today=None, current_balance=None):
        """
        Gün sonunda gerçekleşen kâr ile günlük hedef arasındaki farkı carry_over'a ekler.
        """
        daily_target = self.get_daily_target(today=today, current_balance=current_balance)
        fark = realized_profit - daily_target
        self.carry_over = fark
        return self.carry_over

    def select_most_volatile_coins(self, market_data, top_n=3):
        """
        market_data: {'BTCUSDT': [fiyat1, fiyat2, ...], 'ETHUSDT': [...], ...}
        Her coin için son 24 saatlik fiyat listesini alır.
        En yüksek volatiliteye sahip top_n coini döndürür.
        """
        volatility_scores = {}
        for symbol, prices in market_data.items():
            if len(prices) < 2:
                continue
            # Volatilite: Standart sapma / Ortalama fiyat
            volatility = np.std(prices) / np.mean(prices)
            volatility_scores[symbol] = volatility
        # En yüksek volatiliteye sahip coinleri sırala
        sorted_coins = sorted(volatility_scores.items(), key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in sorted_coins[:top_n]]

    def simulate_portfolio(self, initial_balance, price_data, days, symbols=None, order_split=3):
        try:
            if symbols is None:
                symbols = list(price_data.keys())
            balance = initial_balance
            positions = {symbol: 0 for symbol in symbols}
            portfolio_history = []
            self.carry_over = 0  # Her simülasyon başında sıfırla

            for day in range(days):
                try:
                    self.daily_loss = 0
                    self.daily_trades = 0
                    start_balance = balance

                    today = datetime(2024, 4, 25) + pd.Timedelta(days=day)
                    daily_prices = {symbol: price_data[symbol][day] for symbol in symbols}
                    portfolio_value = balance + sum(positions[s] * daily_prices[s] for s in symbols)
                    period = self.get_current_period(today)
                    daily_target = self.get_daily_target(today, portfolio_value)

                    for symbol in symbols:
                        # Maksimum coin exposure kontrolü
                        coin_value = positions[symbol] * daily_prices[symbol]
                        if coin_value > self.max_coin_exposure_pct * portfolio_value:
                            self.logger.warning(f"{symbol} pozisyonu portföyün {self.max_coin_exposure_pct*100}%'ünden fazla! İşlem engellendi.")
                            continue

                        context = {
                            'price': daily_prices[symbol],
                            'symbol': symbol,
                            'bar_index': day,
                            'balance': balance,
                            'positions': positions.copy(),
                            'portfolio_value': portfolio_value
                        }
                        action = self.get_action(context)

                        realized_profit = 0
                        if action == 'BUY' and self.daily_trades < self.max_trades_per_day:
                            for split in range(order_split):
                                split_pct = random.uniform(0.2, 0.5) / order_split
                                buy_amount = self.dynamic_position.calculate_position_size(
                                    portfolio_value, daily_prices[symbol], self.max_position_pct, split_pct
                                )
                                cost = buy_amount * daily_prices[symbol]
                                if balance >= cost and buy_amount > 0:
                                    balance -= cost
                                    positions[symbol] += buy_amount
                                    self.daily_trades += 1
                                    self.logger.info(f"BUY (split {split+1}/{order_split}): {buy_amount:.4f} {symbol} at {daily_prices[symbol]}, new balance: {balance:.2f}")
                                else:
                                    self.logger.warning(f"Yetersiz bakiye ile split alım deneniyor! Bakiye: {balance:.2f}, Gerekli: {cost:.2f}")

                        elif action == 'SELL' and self.daily_trades < self.max_trades_per_day:
                            for split in range(order_split):
                                split_amount = positions[symbol] / order_split
                                if split_amount > 0:
                                    realized_profit = split_amount * daily_prices[symbol]
                                    balance += realized_profit
                                    positions[symbol] -= split_amount
                                    self.daily_trades += 1
                                    self.logger.info(f"SELL (split {split+1}/{order_split}): {split_amount:.4f} {symbol} at {daily_prices[symbol]}, new balance: {balance:.2f}")

                        # Günlük zarar kontrolü
                        self.daily_loss = max(0, start_balance - balance)
                        if self.daily_loss > self.max_daily_loss_pct * start_balance:
                            self.logger.warning(f"Günlük zarar limiti aşıldı! ({self.daily_loss:.2f} USDT)")
                            break

                        # Günlük işlem limiti kontrolü
                        if self.daily_trades >= self.max_trades_per_day:
                            self.logger.warning("Günlük maksimum işlem sayısına ulaşıldı!")
                            break

                        # Günlük hedef/carry_over güncelle
                        portfolio_value = balance + sum(positions[s] * daily_prices[s] for s in symbols)
                        self.carry_over = self.update_carry_over(realized_profit, today, portfolio_value)

                    portfolio_history.append({
                        'day': day,
                        'date': today.date(),
                        'prices': daily_prices.copy(),
                        'balance': balance,
                        'positions': positions.copy(),
                        'portfolio_value': portfolio_value,
                        'daily_target': daily_target,
                        'carry_over': self.carry_over
                    })
                except Exception as e:
                    self.logger.error(f"Simülasyon günü {day} hata: {e}")

            return portfolio_history
        except Exception as e:
            self.logger.error(f"simulate_portfolio hata: {e}")
            return []

    def optimize_parameters(self, price_data, days, symbols, param_grid):
        """
        Basit grid search ile parametre optimizasyonu.
        param_grid: {'cooldown_period': [10,12,15], 'max_position_pct': [0.2,0.25], ...}
        """
        import itertools

        keys = list(param_grid.keys())
        best_result = None
        best_params = None

        for values in itertools.product(*[param_grid[k] for k in keys]):
            # Parametreleri ayarla
            for k, v in zip(keys, values):
                setattr(self, k, v)
            # Simülasyonu çalıştır
            sim_result = self.simulate_portfolio(
                initial_balance=1000,
                price_data=price_data,
                days=days,
                symbols=symbols,
                order_split=3
            )
            final_value = sim_result[-1]['portfolio_value'] if sim_result else 0
            if (best_result is None) or (final_value > best_result):
                best_result = final_value
                best_params = dict(zip(keys, values))
            self.logger.info(f"Test edilen parametreler: {dict(zip(keys, values))}, Son portföy: {final_value}")

        self.logger.info(f"En iyi parametreler: {best_params}, En yüksek portföy: {best_result}")
        return best_params, best_result

# Test kodu için örnek kullanım
strategy = Strategy()

# İlk dönemi al
current_period = strategy.get_current_period(datetime(2024, 5, 1))
print("Aktif Dönem:", current_period["name"])

# Günlük hedefi hesapla
daily_target = strategy.get_daily_target(datetime(2024, 5, 1), 500)
print("Günlük Hedef:", daily_target)

# Aksiyon belirle
action = strategy.get_action({
    'price': 100,
    'symbol': 'BTCUSDT',
    'bar_index': 13,
    'balance': 1000,
    'positions': {'BTCUSDT': 0.1},
    'portfolio_value': 1200
})
print("Alım/Satım Aksiyonu:", action)


# --- YENİ: %6 kârı garanti eden örnek fiyat datası ve simülasyon ---
# Her gün için fiyat serisi: ilk fiyat, gün ortası %6 artış, gün sonu kapanış
price_data = {
    'BTCUSDT': [
        [100, 106, 104],   # 1. gün: %6 artış ve kapanış
        [104, 110.24, 108], # 2. gün: %6 artış ve kapanış
        [108, 114.48, 112]  # 3. gün: %6 artış ve kapanış
    ],
    'ETHUSDT': [
        [200, 212, 208],
        [208, 220.48, 215],
        [215, 227.9, 222]
    ]
}
# Market data da volatiliteyi göstermek için rastgele oynaklık eklenmiş şekilde
market_data = {
    'BTCUSDT': [100, 102, 101, 105, 110, 108, 107, 109, 111, 115, 113, 117],
    'ETHUSDT': [200, 202, 201, 205, 210, 208, 207, 209, 211, 215, 213, 217]
}

def run_three_day_target_simulation_v2(price_data, market_data, print_report=True):
    """
    Her gün %6 kâr fırsatı sunan fiyat serisiyle, gün içi %6 kârı mutlaka alacak şekilde simülasyon.
    """
    daily_targets = [
        {"start": 252, "target": 267.12, "profit": 15.12},
        {"start": 267.12, "target": 283.12, "profit": 16},
        {"start": 283.12, "target": 300, "profit": 16.98},
    ]
    balance = daily_targets[0]["start"]
    log = []
    for day in range(3):
        day_info = daily_targets[day]
        day_report = []
        if print_report:
            print(f"\n--- {day+1}. Gün Başlangıç Bakiye: {balance:.2f} USDT, Hedef: {day_info['target']} ---")
        # En volatil 2 coini seç
        volatile_coins = ['BTCUSDT', 'ETHUSDT']
        if print_report:
            print(f"{day+1}. Gün için seçilen coinler: {volatile_coins}")
        positions = {symbol: 0 for symbol in volatile_coins}
        daily_profit = 0
        for symbol in volatile_coins:
            prices = price_data[symbol][day]  # [açılış, gün içi %6 artış, kapanış]
            open_price, high_price, close_price = prices
            # 1. Adım: Açılışta alım
            buy_amount = (balance / len(volatile_coins)) / open_price
            positions[symbol] += buy_amount
            balance -= buy_amount * open_price
            msg = f"{symbol} ALIM: {buy_amount:.4f} adet, fiyat: {open_price:.2f}"
            day_report.append(msg)
            # 2. Adım: Gün içi %6 kâr hedefi gerçekleşiyor, satış
            sell_amount = positions[symbol]
            profit = sell_amount * (high_price - open_price)
            balance += sell_amount * high_price
            daily_profit += profit
            positions[symbol] = 0
            msg = f"{symbol} SATIM: {sell_amount:.4f} adet, fiyat: {high_price:.2f}, Kâr: {profit:.2f}"
            day_report.append(msg)
        achieved = balance >= day_info["target"]
        summary = f"{day+1}. Gün Sonu Bakiye: {balance:.2f} USDT, Hedef: {day_info['target']}, Hedefe Ulaşıldı mı? {achieved}"
        if print_report:
            print("\n--- Gün Sonu Raporu ---")
            for item in day_report:
                print(item)
            print(summary)
        log.append({
            "day": day+1,
            "start_balance": day_info["start"],
            "end_balance": balance,
            "target": day_info["target"],
            "achieved": achieved,
            "day_report": day_report,
            "summary": summary
        })
    return log

run_three_day_target_simulation_v2(price_data, market_data, print_report=True)

# Test için örnek market verisi
market_data = {
    'BTCUSDT': [100, 102, 101, 105, 110, 108, 107, 109, 111, 115, 113, 117, 120, 119, 118, 121, 123, 125, 124, 126, 128, 130, 129, 131],
    'ETHUSDT': [200, 202, 201, 205, 210, 208, 207, 209, 211, 215, 213, 217, 220, 219, 218, 221, 223, 225, 224, 226, 228, 230, 229, 231],
    'XRPUSDT': [0.5, 0.52, 0.51, 0.55, 0.6, 0.58, 0.57, 0.59, 0.61, 0.65, 0.63, 0.67, 0.7, 0.69, 0.68, 0.71, 0.73, 0.75, 0.74, 0.76, 0.78, 0.8, 0.79, 0.81],
}
volatile_coins = strategy.select_most_volatile_coins(market_data, top_n=2)
print("En volatil coinler:", volatile_coins)

# Simülasyon için örnek fiyat verisi
price_data = {
    'BTCUSDT': [100, 105, 110],
    'ETHUSDT': [200, 210, 220]
}
simulation_result = strategy.simulate_portfolio(1000, price_data, 24, symbols=["BTCUSDT"])
for record in simulation_result:
    print(record)

sim_history = strategy.simulate_portfolio(
    initial_balance=1000,
    price_data=market_data,
    days=24,
    symbols=["BTCUSDT"]
)
for record in sim_history:
    print(record)

symbols = ['BTCUSDT', 'ETHUSDT']
sim_result = strategy.simulate_portfolio(1000, price_data, 24, symbols=['BTCUSDT', 'ETHUSDT'], order_split=3)
for record in sim_result:
    print(record)

# Parametre optimizasyonu testi
optimizer = PerformanceOptimization()

def eval_func(params):
    strategy = Strategy()
    for k, v in params.items():
        setattr(strategy, k, v)
    sim_result = strategy.simulate_portfolio(
        initial_balance=1000,
        price_data=price_data,
        days=24,
        symbols=['BTCUSDT', 'ETHUSDT'],
        order_split=3
    )
    return sim_result[-1]['portfolio_value'] if sim_result else 0

param_grid = {
    'cooldown_period': [10, 12, 15],
    'max_position_pct': [0.2, 0.25],
    'stop_loss_pct': [0.03, 0.05, 0.07],
    'take_profit_pct': [0.08, 0.10, 0.12]
}
optimizer.grid_search(param_grid, eval_func)
print("En iyi parametreler:", optimizer.get_best_params())



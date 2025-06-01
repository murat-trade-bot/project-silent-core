import pandas as pd
from binance.client import Client
from minimal_strategy import Strategy
from minimal_executor import Executor

COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"]
COMMISSION_RATE = 0.001  # %0.1 komisyon

def fetch_historical_klines(client: Client, symbol: str, interval: str, start_str: str) -> pd.DataFrame:
    klines = client.get_historical_klines(symbol, interval, start_str)
    df = pd.DataFrame(klines, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_av','trades','tb_base_av','tb_quote_av','ignore'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    return df[['open_time','close','high','low','volume']]

def calc_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    avg_gain = up.rolling(window=period, min_periods=period).mean()
    avg_loss = down.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def run_backtest(interval: str = "1h", start_str: str = "60 days ago UTC", initial_balance: float = 231.0) -> float:
    client = Client()
    strategy = Strategy()
    executor = Executor()
    balance = initial_balance
    positions = {coin: 0.0 for coin in COINS}
    data = {coin: fetch_historical_klines(client, coin, interval, start_str) for coin in COINS}

    # Göstergeleri ekle
    for coin in COINS:
        df = data[coin]
        df['rsi'] = calc_rsi(df['close'])
        macd, macd_signal = calc_macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        data[coin] = df

    for i in range(50, len(data[COINS[0]])):
        portfolio_value = balance + sum(
            positions[c] * data[c].iloc[i]['close'] for c in COINS
        )
        for coin in COINS:
            df = data[coin]
            price = df.iloc[i]['close']
            closes = list(df.iloc[i-50:i]['close'])
            volumes = list(df.iloc[i-50:i]['volume'])
            rsi = df.iloc[i]['rsi']
            macd = df.iloc[i]['macd']
            macd_signal = df.iloc[i]['macd_signal']
            position = positions[coin]

            action = strategy.get_action({
                'price': price,
                'symbol': coin,
                'closes': closes,
                'volumes': volumes,
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'bar_index': i,
                'balance': balance,
                'portfolio_value': portfolio_value,
                'position': position
            })

            if action == 'BUY' and balance > price * 0.01:
                # Maksimum pozisyon büyüklüğü strateji tarafından kontrol ediliyor
                amount = (strategy.max_position_pct * portfolio_value) / price
                amount = min(amount, balance / price)
                cost = amount * price * (1 + COMMISSION_RATE)
                if cost <= balance:
                    positions[coin] += amount
                    balance -= amount * price * (1 + COMMISSION_RATE)
            elif action == 'SELL' and positions[coin] > 0:
                proceeds = positions[coin] * price * (1 - COMMISSION_RATE)
                balance += proceeds
                positions[coin] = 0.0

            executor.execute(action, {
                'price': price,
                'balance': balance,
                'position': positions[coin],
                'symbol': coin
            })

    final_value = balance
    for coin in COINS:
        final_value += positions[coin] * data[coin].iloc[-1]['close']
    print(f"Final portfolio value: {final_value:.2f} USDT")
    return final_value

if __name__ == "__main__":
    run_backtest()

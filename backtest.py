import pandas as pd
from binance.client import Client
 from minimal_strategy import Strategy
from core.executor import ExecutorManager

def fetch_historical_klines(client: Client, symbol: str, interval: str, start_str: str) -> pd.DataFrame:
    """
    Binance API üzerinden tarihsel OHLCV verisini pandas DataFrame olarak getirir.
    """
    klines = client.get_historical_klines(symbol, interval, start_str)
    df = pd.DataFrame(klines, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_av','trades','tb_base_av','tb_quote_av','ignore'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    return df[['open_time','close']]

def run_backtest(symbol: str = "BTCUSDT", interval: str = "1h", start_str: str = "1 day ago UTC", initial_balance: float = 100.0) -> float:
    """
    Tarihsel veri üzerinde basit backtest:
      1. Fiyatlar üzerinden döngü kurar
      2. Strategy ile aksiyon alır
      3. ExecutorManager ile işlem simüle eder
      4. Son portföy değerini döndürür
    """
    # Binance client ve veri çekimi
    client = Client()
    df = fetch_historical_klines(client, symbol, interval, start_str)

    balance = initial_balance
    position = 0.0
    strategy = Strategy()
    executor = ExecutorManager(client)  # Binance client parametresiyle başlat

    for _, row in df.iterrows():
        price = row['close']
        action = strategy.get_action({'price': price})

        if action == 'BUY' and balance > 0:
            position = balance / price
            balance = 0.0
        elif action == 'SELL' and position > 0:
            balance = position * price
            position = 0.0

        executor.execute(action, {
            'price': price,
            'balance': balance,
            'position': position
        })

    final_value = balance if balance > 0 else position * df.iloc[-1]['close']
    print(f"Final portfolio value: {final_value}")
    return final_value

if __name__ == "__main__":
    run_backtest()

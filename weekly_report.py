import pandas as pd
from datetime import datetime, timedelta

"""
Weekly report generator: reads trade history and outputs buy/sell trades from the last 7 days.
"""

def generate_weekly_report(csv_path='trades_history.csv') -> pd.DataFrame:
    # Load CSV
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Hata: CSV dosyası bulunamadı: {csv_path}")
        return pd.DataFrame()

    # Check required columns
    required_cols = {'timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl'}
    if not required_cols.issubset(df.columns):
        # CSV formatında eksik sütun var, rapor oluşturulamıyor
        return pd.DataFrame()

    # Parse timestamp to UTC-aware datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df = df.dropna(subset=['timestamp'])

    # Filter for last 7 days
    one_week_ago = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
    weekly = df[df['timestamp'] >= one_week_ago]

    return weekly[['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']]

if __name__ == '__main__':
    print("\n=== Haftalık Al/Sat Raporu (Son 7 Gün) ===")
    report_df = generate_weekly_report()
    if report_df.empty:
        print("Bu hafta işlem bulunamadı.")
    else:
        report_df['timestamp'] = report_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        print(report_df.to_string(index=False))

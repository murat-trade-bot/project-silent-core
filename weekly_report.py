import pandas as pd
from datetime import datetime, timedelta

"""
Weekly report generator: reads trade history and outputs buy/sell trades from the last 7 days.
"""
def generate_weekly_report(csv_path='trades_history.csv') -> pd.DataFrame:
    # CSV'deki zaman sütunu ISO formatında timestamp olarak kayıtlı olmalı
    df = pd.read_csv(csv_path, parse_dates=['timestamp'])
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    weekly = df[df['timestamp'] >= one_week_ago]
    # Sadece gerekli sütunlar
    report = weekly[['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']]
    return report

if __name__ == '__main__':
    report_df = generate_weekly_report()
    print("\n=== Haftalık Al/Sat Raporu (Son 7 Gün) ===")
    if report_df.empty:
        print("Bu hafta işlem bulunamadı.")
    else:
        print(report_df.to_string(index=False))

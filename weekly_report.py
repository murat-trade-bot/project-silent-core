import pandas as pd
from datetime import timedelta

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

    # Ensure timestamp column and parse to UTC-aware datetime
    if 'timestamp' not in df.columns:
        print("Hata: 'timestamp' sütunu CSV'de bulunamadı.")
        return pd.DataFrame()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df = df.dropna(subset=['timestamp'])

    # Filter for last 7 days
    one_week_ago = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
    weekly = df[df['timestamp'] >= one_week_ago]

    # Determine available columns
    expected_cols = ['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']
    present_cols = [col for col in expected_cols if col in weekly.columns]
    missing_cols = set(expected_cols) - set(present_cols)
    if missing_cols:
        print(f"Uyarı: CSV'de aşağıdaki sütunlar eksik, rapora dahil edilmedi: {', '.join(missing_cols)}")
        if not present_cols:
            print("Rapor oluşturmak için yeterli veri bulunamadı.")
            return pd.DataFrame()

    return weekly[present_cols]

if __name__ == '__main__':
    print("\n=== Haftalık Al/Sat Raporu (Son 7 Gün) ===")
    report_df = generate_weekly_report()
    if report_df.empty:
        print("Bu hafta işlem bulunamadı veya gerekli sütunlar eksik.")
    else:
        # Format timestamp if present
        if 'timestamp' in report_df.columns:
            report_df['timestamp'] = report_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        print(report_df.to_string(index=False))

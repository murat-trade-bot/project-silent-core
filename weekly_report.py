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
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Ensure timestamp column exists and convert to datetime (UTC-aware)
    if 'timestamp' not in df.columns:
        raise ValueError("'timestamp' column is required in CSV for weekly report.")
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    # Drop rows where timestamp could not be parsed
    df = df.dropna(subset=['timestamp'])

    # Filter for last 7 days using UTC-aware Timestamp
    one_week_ago = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
    weekly = df[df['timestamp'] >= one_week_ago]

    # Select only relevant columns
    report = weekly[['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']]
    return report

if __name__ == '__main__':
    report_df = generate_weekly_report()
    print("\n=== Haftalık Al/Sat Raporu (Son 7 Gün) ===")
    if report_df.empty:
        print("Bu hafta işlem bulunamadı.")
    else:
        # Format timestamp for readability
        report_df['timestamp'] = report_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        print(report_df.to_string(index=False))

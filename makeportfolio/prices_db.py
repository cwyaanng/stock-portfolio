import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os 

DB_PATH = "prices.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_price (
        date   DATE NOT NULL,
        ticker TEXT NOT NULL,
        close  REAL NOT NULL,
        PRIMARY KEY (date, ticker)
    )
    """)
    conn.commit()
    conn.close()

def save_prices_to_db(prices: pd.DataFrame):
    """prices: DataFrame(index=date, columns=tickers, values=close)"""
    conn = sqlite3.connect(DB_PATH)
    df = prices.reset_index().melt(id_vars="Date", var_name="ticker", value_name="close")
    df.rename(columns={"Date": "date"}, inplace=True)
    df.to_sql("prices", conn, if_exists="append", index=False)
    conn.close()

def load_prices_from_db(tickers, start, end):
  
    print("="*60)
    print(f"[DEBUG] DB_PATH: {os.path.abspath(DB_PATH)}")
    print(f"[DEBUG] tickers ({len(tickers)}): {tickers[:10]}{'...' if len(tickers) > 10 else ''}")
    print(f"[DEBUG] start={start}, end={end}")

    conn = sqlite3.connect(DB_PATH)

    q = f"""
    SELECT date, ticker, close
    FROM portfolio_price
    WHERE date BETWEEN ? AND ?
      AND ticker IN ({",".join("?"*len(tickers))})
    """

    params = [start, end] + tickers
    print("[DEBUG] SQL:", q)
    print("[DEBUG] params:", params)

    df = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    conn.close()

    print(f"[DEBUG] Rows fetched: {df.shape[0]}")
    if not df.empty:
        print(f"[DEBUG] Date range in result: {df['date'].min()} ~ {df['date'].max()}")
        print(f"[DEBUG] Sample tickers in result: {df['ticker'].unique()[:5]}")

    print("="*60)

    return df.pivot(index="date", columns="ticker", values="close") if not df.empty else df


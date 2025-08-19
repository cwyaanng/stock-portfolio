
import pandas as pd
from django.db import connection, transaction

def ensure_table():
    with connection.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_price (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            ticker VARCHAR(12) NOT NULL,
            close REAL NOT NULL,
            UNIQUE(date, ticker)
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS portfolio_price_date_idx ON portfolio_price(date)")
        cur.execute("CREATE INDEX IF NOT EXISTS portfolio_price_ticker_idx ON portfolio_price(ticker)")

@transaction.atomic
def upsert_prices_df(px: pd.DataFrame):
    """
    px: DataFrame(index=Date, columns=tickers, values=close)
    INSERT OR REPLACE 로 upsert
    """
    df = px.reset_index().melt(id_vars="Date", var_name="ticker", value_name="close")
    df.rename(columns={"Date": "date"}, inplace=True)
    rows = [(str(d.date() if hasattr(d, 'date') else d), t, float(c)) for d,t,c in df.itertuples(index=False)]
    with connection.cursor() as cur:
        cur.executemany(
            "INSERT OR REPLACE INTO portfolio_price (date, ticker, close) VALUES (?, ?, ?)",
            rows
        )

def load_prices_pivot(tickers, start: str, end: str) -> pd.DataFrame:
    placeholders = ",".join("?" * len(tickers))
    sql = f"""
    SELECT date, ticker, close
    FROM portfolio_price
    WHERE date BETWEEN ? AND ?
      AND ticker IN ({placeholders})
    """
    params = [start, end] + list(tickers)
    df = pd.read_sql(sql, connection, params=params, parse_dates=["date"])
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="date", columns="ticker", values="close").sort_index()

def get_max_date() -> str | None:
    with connection.cursor() as cur:
        cur.execute("SELECT MAX(date) FROM portfolio_price")
        row = cur.fetchone()
    return row[0] if row and row[0] else None

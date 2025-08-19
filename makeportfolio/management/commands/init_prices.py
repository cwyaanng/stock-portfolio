from django.core.management.base import BaseCommand
from makeportfolio.db_io import ensure_table, upsert_prices_df
from makeportfolio.utils import download_prices
from makeportfolio.universe import NASDAQ100   # 리스트 모듈 

class Command(BaseCommand):
    help = "Initialize DB with 1y NASDAQ100 adjusted close"

    def handle(self, *args, **opts):
        ensure_table()
        prices = download_prices(NASDAQ100)  # default: 최근 1년
        if prices.empty:
            self.stderr.write("No prices downloaded.")
            return
        upsert_prices_df(prices)
        self.stdout.write(self.style.SUCCESS(
            f"Inserted {prices.shape[0]} rows × {prices.shape[1]} tickers (pivot) into portfolio_price"
        ))

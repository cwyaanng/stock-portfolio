from django.core.management.base import BaseCommand
from datetime import date, timedelta
from makeportfolio.db_io import ensure_table, upsert_prices_df, get_max_date
from makeportfolio.utils import download_prices
from makeportfolio.universe import NASDAQ100

class Command(BaseCommand):
    help = "Incremental update (from last stored date + 1 day to today)"

    def handle(self, *args, **opts):
        ensure_table()
        max_d = get_max_date()
        if max_d is None:
            self.stdout.write("No existing data. Run `manage.py init_prices` first.")
            return

        start = (date.fromisoformat(max_d) + timedelta(days=1)).isoformat()
        end = date.today().isoformat()
        if start > end:
            self.stdout.write("Already up-to-date.")
            return

        prices = download_prices(NASDAQ100, start=start, end=end)
        if prices.empty:
            self.stdout.write("No new rows to insert.")
            return

        upsert_prices_df(prices)
        self.stdout.write(self.style.SUCCESS(f"Updated to {end}"))

from django.db import models

class Price(models.Model):
    date = models.DateField()
    ticker = models.CharField(max_length=12)
    close = models.FloatField()

    class Meta:
        unique_together = ("date", "ticker")
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["ticker"]),
        ]

    def __str__(self):
        return f"{self.date} {self.ticker} {self.close}"

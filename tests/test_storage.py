from datetime import datetime, timezone
from decimal import Decimal

from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData


def test_save_and_read_latest(tmp_path):
    storage = PriceStorage(tmp_path / "nested" / "prices.db")
    storage.initialize()
    checked_at = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    price = PriceData(
        "Wipes",
        "baby",
        "fake",
        Decimal("20"),
        Decimal("15"),
        Decimal("5.00"),
        Decimal("25.00"),
        "USD",
        True,
        "fake://wipes?original=20&current=15",
        checked_at,
    )
    storage.save(price)
    assert storage.latest() == [price]


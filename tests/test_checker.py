from decimal import Decimal

from price_tracker.adapters.base import AdapterError
from price_tracker.adapters.fake import FakeAdapter, fake_transport
from price_tracker.database.storage import PriceStorage
from price_tracker.models.product import Product, ProductCatalog, StoreConfig
from price_tracker.services.checker import PriceChecker
from price_tracker.utils.http_client import HttpClient, HttpClientError


def _http_client() -> HttpClient:
    return HttpClient(transports={"fake": fake_transport})


def test_checker_skips_disabled_and_stores_successes(tmp_path):
    catalog = ProductCatalog(
        (
            Product(
                "Enabled",
                "other",
                True,
                {"fake": StoreConfig("fake://one?original=10&current=8")},
                Decimal("10"),
            ),
            Product(
                "Disabled",
                "other",
                False,
                {"fake": StoreConfig("fake://two?original=10&current=5")},
                Decimal("10"),
            ),
        ),
    )
    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    results = PriceChecker(
        storage, {"fake": FakeAdapter()}, _http_client()
    ).check(catalog)
    assert [item.product_name for item in results] == ["Enabled"]
    assert [item.product_name for item in storage.latest()] == ["Enabled"]


def test_checker_continues_after_adapter_failure(tmp_path, caplog):
    catalog = ProductCatalog(
        (
            Product(
                "Bad",
                "other",
                True,
                {"fake": StoreConfig("fake://bad")},
                Decimal("10"),
            ),
            Product(
                "Good",
                "other",
                True,
                {"fake": StoreConfig("fake://good?original=10&current=9")},
                Decimal("10"),
            ),
        ),
    )
    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    results = PriceChecker(
        storage, {"fake": FakeAdapter()}, _http_client()
    ).check(catalog)
    assert [item.product_name for item in results] == ["Good"]
    assert "Price check failed for Bad" in caplog.text
    assert "valid original and current prices" in caplog.text


def test_checker_handles_custom_adapter_error(tmp_path, caplog):
    class FailingAdapter(FakeAdapter):
        store_name = "failing"

        def parse(self, html: str, product_config: Product):
            raise AdapterError("fixture fetch failed")

    catalog = ProductCatalog(
        (
            Product(
                "Failure",
                "other",
                True,
                {"failing": StoreConfig("fake://failure")},
            ),
        )
    )
    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    assert (
        PriceChecker(
            storage,
            {"failing": FailingAdapter()},
            _http_client(),
        ).check(catalog)
        == []
    )
    assert "fixture fetch failed" in caplog.text


def test_checker_handles_network_error_without_parsing(tmp_path, caplog):
    class FailingHttpClient(HttpClient):
        def fetch(self, url: str) -> str:
            raise HttpClientError("connection timed out")

    catalog = ProductCatalog(
        (
            Product(
                "Offline",
                "other",
                True,
                {"fake": StoreConfig("fake://offline")},
            ),
        )
    )
    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    checker = PriceChecker(
        storage, {"fake": FakeAdapter()}, FailingHttpClient()
    )
    results = checker.check(catalog)
    assert results == []
    assert checker.last_stats.products_checked == 1
    assert checker.last_stats.successful_checks == 0
    assert checker.last_stats.errors == 1
    assert "connection timed out" in caplog.text

from decimal import Decimal

import pytest

from price_tracker.adapters.base import AdapterError, StoreAdapter
from price_tracker.adapters.fake import FakeAdapter
from price_tracker.models.product import Product, StoreConfig


def _product() -> Product:
    return Product(
        name="Nappies",
        category="baby",
        enabled=True,
        stores={},
        notification_threshold=Decimal("10"),
    )


def test_fake_adapter_normalizes_url_values():
    adapter = FakeAdapter()
    assert isinstance(adapter, StoreAdapter)
    result = adapter.parse(
        "fake://nappies?original=50&current=42.50&available=false&currency=cad",
        _product(),
    )
    assert result.product_name == "Nappies"
    assert result.store == "fake"
    assert result.discount_amount == Decimal("7.50")
    assert result.discount_percent == Decimal("15.00")
    assert result.currency == "CAD"
    assert result.availability is False


def test_fake_adapter_rejects_missing_prices():
    with pytest.raises(AdapterError, match="original and current"):
        FakeAdapter().parse("fake://nappies", _product())


def test_fake_adapter_parses_saved_source_without_network():
    result = FakeAdapter().parse(
        "fake://nappies?original=20&current=15", _product()
    )
    assert result.current_price == Decimal("15")


def test_fake_adapter_wraps_invalid_price_as_adapter_error():
    with pytest.raises(AdapterError, match="invalid prices"):
        FakeAdapter().parse(
            "fake://nappies?original=-1&current=1", _product()
        )

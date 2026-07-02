from decimal import Decimal

import pytest

from price_tracker.services.discount import calculate_discount


def test_calculate_discount():
    amount, percent = calculate_discount(Decimal("40"), Decimal("30"))
    assert amount == Decimal("10.00")
    assert percent == Decimal("25.00")


def test_price_increase_is_not_a_discount():
    assert calculate_discount(Decimal("10"), Decimal("12")) == (
        Decimal("0.00"),
        Decimal("0.00"),
    )


def test_negative_price_is_invalid():
    with pytest.raises(ValueError):
        calculate_discount(Decimal("-1"), Decimal("1"))


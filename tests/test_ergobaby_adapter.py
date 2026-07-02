from decimal import Decimal
from pathlib import Path

import pytest

from price_tracker.adapters.base import AdapterError
from price_tracker.adapters.ergobaby import ErgobabyAdapter
from price_tracker.models.product import OptionStrategy, Product, StoreConfig

FIXTURE = (
    Path(__file__).parent / "fixtures" / "ergobaby" / "omni_deluxe.html"
)
URL = "https://ergobaby.com/en-us/products/omni-deluxe-baby-carrier"


def _product(
    strategy: OptionStrategy, options: dict[str, str] | None = None
) -> Product:
    return Product(
        name="Ergobaby Omni Deluxe Mesh Baby Carrier",
        category="baby",
        enabled=True,
        stores={"ergobaby": StoreConfig(url=URL)},
        option_strategy=strategy,
        options=options or {},
    )


def test_parse_specific_available_variant_and_discount() -> None:
    price = ErgobabyAdapter().parse(
        FIXTURE.read_text(encoding="utf-8"),
        _product(
            OptionStrategy.SPECIFIC_OPTIONS,
            {"fabric": "Mesh", "color": "Pearl Grey"},
        ),
    )

    assert price.product_name.endswith("Mesh / Pearl Grey")
    assert price.original_price == Decimal("219")
    assert price.current_price == Decimal("179")
    assert price.discount_amount == Decimal("40.00")
    assert price.discount_percent == Decimal("18.26")
    assert price.currency == "USD"
    assert price.availability is True
    assert price.product_url.endswith("variant=1")
    assert price.tied_variants == ()


def test_lowest_price_captures_tied_matching_mesh_variants() -> None:
    price = ErgobabyAdapter().parse(
        FIXTURE.read_text(encoding="utf-8"),
        _product(
            OptionStrategy.LOWEST_PRICE,
            {"fabric": "Mesh", "color": "any"},
        ),
    )

    assert price.product_name.endswith("Mesh / Soft Olive")
    assert price.current_price == Decimal("159")
    assert price.original_price == Decimal("159")
    assert price.availability is True
    assert price.tied_variants == ("Natural Beige",)


def test_lowest_price_ignores_cheaper_unavailable_variant() -> None:
    price = ErgobabyAdapter().parse(
        FIXTURE.read_text(encoding="utf-8"),
        _product(OptionStrategy.LOWEST_PRICE, {"fabric": "Mesh"}),
    )

    assert not price.product_name.endswith("Mesh / Onyx Black")
    assert price.current_price == Decimal("159")
    assert price.availability is True
    assert price.tied_variants == ("Natural Beige",)


def test_specific_options_rejects_unavailable_match() -> None:
    with pytest.raises(AdapterError, match="matches configured options"):
        ErgobabyAdapter().parse(
            FIXTURE.read_text(encoding="utf-8"),
            _product(
                OptionStrategy.SPECIFIC_OPTIONS,
                {"fabric": "Mesh", "color": "Onyx Black"},
            ),
        )


def test_all_options_currently_returns_lowest_available_variant() -> None:
    price = ErgobabyAdapter().parse(
        FIXTURE.read_text(encoding="utf-8"),
        _product(OptionStrategy.ALL_OPTIONS),
    )

    assert price.product_name.endswith("Mesh / Soft Olive")
    assert price.current_price == Decimal("159")


def test_parse_rejects_html_without_product_data() -> None:
    with pytest.raises(AdapterError, match="no parseable product variants"):
        ErgobabyAdapter().parse("<html></html>", _product(OptionStrategy.LOWEST_PRICE))

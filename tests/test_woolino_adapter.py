from decimal import Decimal
from pathlib import Path

from price_tracker.adapters.woolino import WoolinoAdapter
from price_tracker.models.product import OptionStrategy, Product, StoreConfig

FIXTURES = Path(__file__).parent / "fixtures" / "woolino"
URL = "https://www.woolino.com/products/sleep-bag"


def _product(
    strategy: OptionStrategy = OptionStrategy.LOWEST_PRICE,
    options: dict[str, str] | None = None,
) -> Product:
    return Product(
        name="Woolino 4 Season Ultimate Sleep Bag",
        category="baby",
        enabled=True,
        stores={"woolino": StoreConfig(URL)},
        option_strategy=strategy,
        options=options or {},
    )


def test_parse_normal_price_ignores_cheaper_unavailable_variant() -> None:
    price = WoolinoAdapter().parse(
        (FIXTURES / "sleep_bag.html").read_text(encoding="utf-8"),
        _product(),
    )

    assert price.product_name.endswith("Baby / 2 Months - 2 Years")
    assert price.selected_variant == "Baby / 2 Months - 2 Years"
    assert price.original_price == Decimal("109")
    assert price.current_price == Decimal("109")
    assert price.discount_amount == Decimal("0.00")
    assert price.discount_percent == Decimal("0.00")
    assert price.currency == "USD"
    assert price.availability is True
    assert price.product_url.endswith("variant=1")


def test_parse_unavailable_product() -> None:
    price = WoolinoAdapter().parse(
        (FIXTURES / "unavailable.html").read_text(encoding="utf-8"),
        _product(),
    )

    assert price.product_name.endswith("Baby / Sold Out")
    assert price.current_price == Decimal("89")
    assert price.availability is False
    assert price.product_url.endswith("variant=9")


def test_specific_options_selects_matching_variant_and_sale_price() -> None:
    price = WoolinoAdapter().parse(
        (FIXTURES / "sleep_bag.html").read_text(encoding="utf-8"),
        _product(
            OptionStrategy.SPECIFIC_OPTIONS,
            {"age": "Toddler", "size": "2 - 4 Years"},
        ),
    )

    assert price.selected_variant == "Toddler / 2 - 4 Years"
    assert price.original_price == Decimal("129")
    assert price.current_price == Decimal("119")
    assert price.discount_amount == Decimal("10.00")
    assert price.discount_percent == Decimal("7.75")
    assert price.availability is True

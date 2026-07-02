from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TypeAlias

OptionValue: TypeAlias = str | int | float | bool | None


class OptionStrategy(StrEnum):
    LOWEST_PRICE = "lowest_price"
    SPECIFIC_OPTIONS = "specific_options"
    ALL_OPTIONS = "all_options"


@dataclass(frozen=True, slots=True)
class StoreConfig:
    url: str


@dataclass(frozen=True, slots=True)
class Product:
    name: str
    category: str
    enabled: bool
    stores: dict[str, StoreConfig]
    notification_threshold: Decimal | None = None
    option_strategy: OptionStrategy = OptionStrategy.LOWEST_PRICE
    options: dict[str, OptionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProductCatalog:
    products: tuple[Product, ...]

    @property
    def enabled_products(self) -> tuple[Product, ...]:
        return tuple(product for product in self.products if product.enabled)

    def threshold_for(
        self, product: Product, default_threshold: Decimal
    ) -> Decimal:
        return (
            product.notification_threshold
            if product.notification_threshold is not None
            else default_threshold
        )

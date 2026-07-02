from typing import Protocol, runtime_checkable

from price_tracker.models.price import PriceData
from price_tracker.models.product import Product


class AdapterError(RuntimeError):
    """A store adapter could not normalize product data."""


@runtime_checkable
class StoreAdapter(Protocol):
    store_name: str

    def parse(self, html: str, product_config: Product) -> PriceData:
        """Convert previously downloaded source into normalized price data."""

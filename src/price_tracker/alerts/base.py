from typing import Protocol, runtime_checkable

from price_tracker.models.price import PriceData
from price_tracker.models.product import Product


@runtime_checkable
class AlertChannel(Protocol):
    def send(self, price: PriceData, product: Product) -> None:
        """Send one discount notification or raise on failure."""

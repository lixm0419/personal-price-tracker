from decimal import Decimal

from price_tracker.alerts.base import AlertChannel
from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData
from price_tracker.models.product import Product


def should_notify(
    price: PriceData,
    threshold: Decimal,
    *,
    already_sent: bool = False,
) -> bool:
    return (
        price.availability
        and price.discount_percent >= threshold
        and not already_sent
    )


class NotificationService:
    def __init__(
        self,
        storage: PriceStorage,
        channels: tuple[AlertChannel, ...],
        *,
        record_sent: bool = True,
    ) -> None:
        self.storage = storage
        self.channels = channels
        self.record_sent = record_sent

    def notify(
        self, price: PriceData, product: Product, threshold: Decimal
    ) -> bool:
        if not should_notify(
            price,
            threshold,
            already_sent=self.storage.notification_was_sent(price),
        ):
            return False
        for channel in self.channels:
            channel.send(price, product)
        if self.record_sent:
            self.storage.record_notification(price)
        return True

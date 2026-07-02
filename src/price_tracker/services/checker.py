import logging
from decimal import Decimal

from price_tracker.alerts.service import NotificationService
from price_tracker.adapters.base import AdapterError, StoreAdapter
from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData
from price_tracker.models.product import ProductCatalog
from price_tracker.utils.http_client import HttpClient, HttpClientError

LOGGER = logging.getLogger(__name__)


class PriceChecker:
    def __init__(
        self,
        storage: PriceStorage,
        adapters: dict[str, StoreAdapter],
        http_client: HttpClient,
        notification_service: NotificationService | None = None,
        default_notification_threshold: Decimal = Decimal("10"),
    ) -> None:
        self.storage = storage
        self.adapters = adapters
        self.http_client = http_client
        self.notification_service = notification_service
        self.default_notification_threshold = default_notification_threshold

    def check(self, catalog: ProductCatalog) -> list[PriceData]:
        results: list[PriceData] = []
        for product in catalog.enabled_products:
            for store, store_config in product.stores.items():
                adapter = self.adapters.get(store)
                if adapter is None:
                    LOGGER.error("No adapter registered for store '%s'", store)
                    continue
                try:
                    html = self.http_client.fetch(store_config.url)
                    price = adapter.parse(html, product)
                except HttpClientError as exc:
                    LOGGER.error(
                        "Download failed for %s at %s: %s",
                        product.name,
                        store,
                        exc,
                    )
                    continue
                except AdapterError as exc:
                    LOGGER.error(
                        "Price check failed for %s at %s: %s",
                        product.name,
                        store,
                        exc,
                    )
                    continue
                except Exception as exc:
                    error = AdapterError(
                        f"Unexpected parser failure in '{store}': {exc}"
                    )
                    LOGGER.error(
                        "Price check failed for %s at %s: %s",
                        product.name,
                        store,
                        error,
                    )
                    continue
                self.storage.save(price)
                results.append(price)
                if self.notification_service is not None:
                    try:
                        self.notification_service.notify(
                            price,
                            product,
                            catalog.threshold_for(
                                product, self.default_notification_threshold
                            ),
                        )
                    except Exception as exc:
                        LOGGER.error(
                            "Notification failed for %s at %s: %s",
                            product.name,
                            store,
                            exc,
                        )
        return results

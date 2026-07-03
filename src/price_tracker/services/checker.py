import logging
from dataclasses import dataclass, field
from decimal import Decimal

from price_tracker.alerts.service import NotificationService
from price_tracker.adapters.base import AdapterError, StoreAdapter
from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData
from price_tracker.models.product import Product, ProductCatalog
from price_tracker.utils.http_client import HttpClient, HttpClientError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NotificationDecision:
    product: Product
    price: PriceData
    sent: bool
    reason_code: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class CheckStats:
    products_checked: int = 0
    successful_checks: int = 0
    notifications_sent: int = 0
    errors: int = 0
    decisions: list[NotificationDecision] = field(default_factory=list)

    def skipped(self, reason_code: str) -> int:
        return sum(
            decision.reason_code == reason_code
            for decision in self.decisions
        )


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
        self.last_stats = CheckStats()

    def check(self, catalog: ProductCatalog) -> list[PriceData]:
        self.last_stats = CheckStats()
        results: list[PriceData] = []
        for product in catalog.enabled_products:
            for store, store_config in product.stores.items():
                self.last_stats.products_checked += 1
                adapter = self.adapters.get(store)
                if adapter is None:
                    LOGGER.error("No adapter registered for store '%s'", store)
                    self.last_stats.errors += 1
                    continue
                try:
                    html = self.http_client.fetch(store_config.url)
                    price = adapter.parse(html, product)
                except HttpClientError as exc:
                    self.last_stats.errors += 1
                    LOGGER.error(
                        "Download failed for %s at %s: %s",
                        product.name,
                        store,
                        exc,
                    )
                    continue
                except AdapterError as exc:
                    self.last_stats.errors += 1
                    LOGGER.error(
                        "Price check failed for %s at %s: %s",
                        product.name,
                        store,
                        exc,
                    )
                    continue
                except Exception as exc:
                    self.last_stats.errors += 1
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
                self.last_stats.successful_checks += 1
                threshold = catalog.threshold_for(
                    product, self.default_notification_threshold
                )
                if self.notification_service is not None:
                    already_sent = self.storage.notification_was_sent(price)
                    try:
                        would_send = self.notification_service.notify(
                            price, product, threshold
                        )
                        is_dry_run = bool(
                            getattr(
                                self.notification_service,
                                "is_dry_run",
                                False,
                            )
                        )
                        sent = would_send and not is_dry_run
                        if sent:
                            self.last_stats.notifications_sent += 1
                        reason_code, reason = self._decision_reason(
                            price,
                            threshold,
                            already_sent,
                            would_send,
                            is_dry_run,
                        )
                        self.last_stats.decisions.append(
                            NotificationDecision(
                                product,
                                price,
                                sent,
                                reason_code,
                                reason,
                            )
                        )
                    except Exception as exc:
                        self.last_stats.errors += 1
                        self.last_stats.decisions.append(
                            NotificationDecision(
                                product,
                                price,
                                False,
                                "error",
                                f"Notification error: {exc}",
                            )
                        )
                        LOGGER.error(
                            "Notification failed for %s at %s: %s",
                            product.name,
                            store,
                            exc,
                        )
                else:
                    self.last_stats.decisions.append(
                        NotificationDecision(
                            product,
                            price,
                            False,
                            "configuration",
                            "Email notifications disabled",
                        )
                    )
        return results

    @staticmethod
    def _decision_reason(
        price: PriceData,
        threshold: Decimal,
        already_sent: bool,
        would_send: bool,
        is_dry_run: bool,
    ) -> tuple[str | None, str | None]:
        if would_send:
            return (
                ("dry_run", "Dry run; no email sent")
                if is_dry_run
                else (None, None)
            )
        if not price.availability:
            return "unavailable", "Product unavailable"
        if price.discount_percent < threshold:
            return (
                "threshold",
                f"Discount below threshold ({price.discount_percent}% < "
                f"{threshold}%)",
            )
        if already_sent:
            return "duplicate", "Duplicate notification"
        return "configuration", "Email configuration unavailable"

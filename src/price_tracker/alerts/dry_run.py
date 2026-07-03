import logging
from decimal import Decimal

from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData
from price_tracker.models.product import Product
from price_tracker.models.settings import EmailSettings

LOGGER = logging.getLogger(__name__)


class DryRunNotificationReporter:
    """Report notification decisions without sending or recording alerts."""

    is_dry_run = True

    def __init__(
        self, storage: PriceStorage, email_settings: EmailSettings
    ) -> None:
        self.storage = storage
        self.email_settings = email_settings
        self.checked = 0
        self.would_notify = 0

    def notify(
        self, price: PriceData, product: Product, threshold: Decimal
    ) -> bool:
        self.checked += 1
        reason = self._skip_reason(price, threshold)
        if reason is None:
            self.would_notify += 1
            LOGGER.info("%s", self._entry(price, product, "WOULD SEND"))
            return True
        LOGGER.info("%s", self._entry(price, product, "SKIPPED", reason))
        return False

    def report_summary(self) -> None:
        LOGGER.info(
            "Notification Summary\n\nChecked: %d\nWould notify: %d\nSkipped: %d",
            self.checked,
            self.would_notify,
            self.checked - self.would_notify,
        )

    def _skip_reason(
        self, price: PriceData, threshold: Decimal
    ) -> str | None:
        if not price.availability:
            return "Product unavailable"
        if price.discount_percent < threshold:
            return (
                "Discount below threshold "
                f"({price.discount_percent}% < {threshold}%)"
            )
        if self.storage.notification_was_sent(price):
            return "Duplicate notification"
        email_issue = self._email_configuration_issue()
        if email_issue is not None:
            return f"Missing email configuration: {email_issue}"
        return None

    def _email_configuration_issue(self) -> str | None:
        settings = self.email_settings
        if not settings.enabled:
            return "email is disabled"
        if not settings.smtp_host:
            return "missing smtp_host"
        for value, variable in (
            (settings.username, settings.username_env),
            (settings.password, settings.password_env),
            (settings.sender, settings.sender_env),
            (settings.recipient, settings.recipient_env),
        ):
            if not value:
                return f"missing environment variable {variable}"
        return None

    @staticmethod
    def _entry(
        price: PriceData,
        product: Product,
        status: str,
        reason: str | None = None,
    ) -> str:
        lines = [
            f"Product: {product.name}",
            f"Store: {price.store}",
            "Selected variant/options: "
            f"{price.selected_variant or 'Not specified'}",
            f"Current price: {price.currency} {price.current_price}",
            f"Original price: {price.currency} {price.original_price}",
            f"Discount: {price.discount_percent}%",
            f"Notification status: {status}",
        ]
        if reason is not None:
            lines.append(f"Reason: {reason}")
        else:
            lines.append(f"Product URL: {price.product_url}")
            if price.tied_variants:
                lines.append(
                    "Tied lowest variants: "
                    + ", ".join(price.tied_variants)
                )
        return "\n".join(lines)

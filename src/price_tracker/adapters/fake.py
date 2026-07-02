from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

from collections.abc import Mapping

from price_tracker.adapters.base import AdapterError
from price_tracker.models.price import PriceData
from price_tracker.models.product import Product
from price_tracker.services.discount import calculate_discount


class FakeAdapter:
    """Deterministic adapter for development and tests; performs no network I/O."""

    store_name = "fake"

    def parse(self, html: str, product_config: Product) -> PriceData:
        url = html
        parsed = urlparse(url)
        values = parse_qs(parsed.query)
        try:
            original = Decimal(values["original"][0])
            current = Decimal(values["current"][0])
        except (KeyError, InvalidOperation, IndexError) as exc:
            raise AdapterError(
                "Fake source requires valid original and current prices"
            ) from exc
        try:
            amount, percent = calculate_discount(original, current)
        except ValueError as exc:
            raise AdapterError(f"Fake source contains invalid prices: {exc}") from exc
        available_text = values.get("available", ["true"])[0].lower()
        if available_text not in {"true", "false"}:
            raise AdapterError("Fake source availability must be true or false")
        currency = values.get("currency", ["USD"])[0].upper()
        return PriceData(
            product_name=product_config.name,
            category=product_config.category,
            store=self.store_name,
            original_price=original,
            current_price=current,
            discount_amount=amount,
            discount_percent=percent,
            currency=currency,
            availability=available_text == "true",
            product_url=url,
            checked_at=datetime.now(timezone.utc),
        )


def fake_transport(
    url: str, timeout: float, headers: Mapping[str, str]
) -> str:
    """Return deterministic fake source without network access."""
    if urlparse(url).scheme != "fake":
        raise ValueError("Fake transport requires a fake:// URL")
    return url

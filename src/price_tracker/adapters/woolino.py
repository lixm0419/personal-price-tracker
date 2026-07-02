import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

from price_tracker.adapters.base import AdapterError
from price_tracker.models.price import PriceData
from price_tracker.models.product import OptionStrategy, Product
from price_tracker.services.discount import calculate_discount


class _WoolinoDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.json_ld: list[Any] = []
        self.variants: list[dict[str, Any]] = []
        self._target: str | None = None
        self._parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if (
            tag == "script"
            and attributes.get("type", "").lower()
            == "application/ld+json"
        ):
            self._target = "json_ld"
            self._parts = []
        elif tag == "textarea" and "data-variant-json" in attributes:
            self._target = "variants"
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._target is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        expected_tag = "script" if self._target == "json_ld" else "textarea"
        if self._target is None or tag != expected_tag:
            return
        target = self._target
        self._target = None
        try:
            document = json.loads("".join(self._parts))
        except json.JSONDecodeError:
            self._parts = []
            return
        self._parts = []
        if target == "json_ld":
            self.json_ld.append(document)
        elif isinstance(document, list):
            self.variants.extend(
                item for item in document if isinstance(item, dict)
            )


@dataclass(frozen=True, slots=True)
class _Variant:
    name: str
    options: str
    sku: str
    original_price: Decimal
    current_price: Decimal
    currency: str
    available: bool
    url: str


class WoolinoAdapter:
    """Normalize Woolino structured product data without performing I/O."""

    store_name = "woolino"

    def parse(self, html: str, product_config: Product) -> PriceData:
        parser = _WoolinoDataParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            raise AdapterError(f"Unable to parse Woolino HTML: {exc}") from exc

        offer_metadata = self._offer_metadata(parser.json_ld)
        variants = [
            variant
            for raw in parser.variants
            if (variant := self._normalize_variant(raw, offer_metadata))
            is not None
        ]
        if not variants:
            raise AdapterError("Woolino page contains no parseable variants")

        selected, ties = self._select_variant(variants, product_config)
        try:
            amount, percent = calculate_discount(
                selected.original_price, selected.current_price
            )
        except ValueError as exc:
            raise AdapterError(f"Woolino page contains invalid prices: {exc}") from exc

        return PriceData(
            product_name=selected.name,
            category=product_config.category,
            store=self.store_name,
            original_price=selected.original_price,
            current_price=selected.current_price,
            discount_amount=amount,
            discount_percent=percent,
            currency=selected.currency,
            availability=selected.available,
            product_url=selected.url or self._configured_url(product_config),
            checked_at=datetime.now(timezone.utc),
            tied_variants=ties,
            selected_variant=selected.options,
        )

    @staticmethod
    def _offer_metadata(
        documents: list[Any],
    ) -> dict[str, tuple[str, str]]:
        metadata: dict[str, tuple[str, str]] = {}
        for document in documents:
            if not isinstance(document, dict) or document.get("@type") != "Product":
                continue
            offers = document.get("offers", [])
            if isinstance(offers, dict):
                offers = [offers]
            if not isinstance(offers, list):
                continue
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                sku = str(offer.get("sku", ""))
                if sku:
                    metadata[sku] = (
                        str(offer.get("priceCurrency", "USD")).upper(),
                        str(offer.get("url", "")),
                    )
        return metadata

    @staticmethod
    def _normalize_variant(
        raw: dict[str, Any],
        offer_metadata: dict[str, tuple[str, str]],
    ) -> _Variant | None:
        try:
            current = Decimal(str(raw["price"])) / Decimal("100")
        except (KeyError, InvalidOperation):
            return None
        compare_at = raw.get("compare_at_price")
        try:
            original = (
                Decimal(str(compare_at)) / Decimal("100")
                if compare_at is not None
                else current
            )
        except InvalidOperation:
            original = current
        sku = str(raw.get("sku", ""))
        currency, url = offer_metadata.get(sku, ("USD", ""))
        options = str(raw.get("public_title") or raw.get("title") or sku)
        return _Variant(
            name=str(raw.get("name") or options or "Woolino product"),
            options=options,
            sku=sku,
            original_price=max(original, current),
            current_price=current,
            currency=currency,
            available=raw.get("available") is True,
            url=url,
        )

    def _select_variant(
        self, variants: list[_Variant], product_config: Product
    ) -> tuple[_Variant, tuple[str, ...]]:
        candidates = variants
        if product_config.option_strategy in {
            OptionStrategy.LOWEST_PRICE,
            OptionStrategy.SPECIFIC_OPTIONS,
        }:
            requested = [
                str(value).strip().casefold()
                for value in product_config.options.values()
                if value is not None
                and str(value).strip().casefold() not in {"", "any"}
            ]
            candidates = [
                variant
                for variant in variants
                if all(
                    value
                    in f"{variant.name} {variant.options} {variant.sku}".casefold()
                    for value in requested
                )
            ]
            if not candidates:
                raise AdapterError(
                    "No Woolino variant matches configured options"
                )

        available = [variant for variant in candidates if variant.available]
        selectable = available or candidates
        selected = min(
            selectable, key=lambda variant: variant.current_price
        )
        if product_config.option_strategy is not OptionStrategy.LOWEST_PRICE:
            return selected, ()
        ties = tuple(
            variant.options
            for variant in selectable
            if variant is not selected
            and variant.current_price == selected.current_price
        )
        return selected, ties

    def _configured_url(self, product_config: Product) -> str:
        store = product_config.stores.get(self.store_name)
        return store.url if store is not None else ""

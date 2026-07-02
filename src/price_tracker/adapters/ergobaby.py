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


class _StructuredDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.documents: list[Any] = []
        self._collecting = False
        self._parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type", "").lower() in {
            "application/json",
            "application/ld+json",
        }:
            self._collecting = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._collecting:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "script" or not self._collecting:
            return
        self._collecting = False
        try:
            self.documents.append(json.loads("".join(self._parts)))
        except json.JSONDecodeError:
            pass
        self._parts = []


@dataclass(frozen=True, slots=True)
class _Variant:
    name: str
    sku: str
    current_price: Decimal
    original_price: Decimal
    currency: str
    available: bool
    url: str


class ErgobabyAdapter:
    """Normalize Ergobaby's static structured product data without fetching it."""

    store_name = "ergobaby"

    def parse(self, html: str, product_config: Product) -> PriceData:
        documents = self._structured_documents(html)
        variants = self._variants(documents)
        if not variants:
            raise AdapterError("Ergobaby page contains no parseable product variants")

        variant, tied_variants = self._select_variant(variants, product_config)
        try:
            amount, percent = calculate_discount(
                variant.original_price, variant.current_price
            )
        except ValueError as exc:
            raise AdapterError(f"Ergobaby page contains invalid prices: {exc}") from exc

        return PriceData(
            product_name=variant.name,
            category=product_config.category,
            store=self.store_name,
            original_price=variant.original_price,
            current_price=variant.current_price,
            discount_amount=amount,
            discount_percent=percent,
            currency=variant.currency,
            availability=variant.available,
            product_url=variant.url or self._configured_url(product_config),
            checked_at=datetime.now(timezone.utc),
            tied_variants=tied_variants,
            selected_variant=self._variant_options(variant),
        )

    @staticmethod
    def _structured_documents(html: str) -> list[Any]:
        parser = _StructuredDataParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            raise AdapterError(f"Unable to parse Ergobaby HTML: {exc}") from exc
        return parser.documents

    def _variants(self, documents: list[Any]) -> list[_Variant]:
        selected = self._selected_variant(documents)
        variants: list[_Variant] = []
        for document in documents:
            if not isinstance(document, dict):
                continue
            if document.get("@type") not in {"Product", "ProductGroup"}:
                continue
            candidates = document.get("hasVariant")
            if not isinstance(candidates, list):
                candidates = [document] if document.get("@type") == "Product" else []
            for candidate in candidates:
                variant = self._variant_from_json_ld(candidate, selected)
                if variant is not None:
                    variants.append(variant)
        return variants

    @staticmethod
    def _selected_variant(documents: list[Any]) -> dict[str, Any] | None:
        for document in documents:
            if not isinstance(document, dict):
                continue
            if {"price", "available", "sku"}.issubset(document):
                return document
        return None

    @staticmethod
    def _variant_from_json_ld(
        candidate: Any, selected: dict[str, Any] | None
    ) -> _Variant | None:
        if not isinstance(candidate, dict):
            return None
        offer = candidate.get("offers")
        if isinstance(offer, list):
            offer = next(
                (item for item in offer if isinstance(item, dict)), None
            )
        if not isinstance(offer, dict):
            return None
        try:
            current = Decimal(str(offer["price"]))
        except (KeyError, InvalidOperation):
            return None

        sku = str(candidate.get("sku", ""))
        original = current
        if selected is not None and str(selected.get("sku", "")) == sku:
            compare_at = selected.get("compare_at_price")
            if compare_at is not None:
                try:
                    original = Decimal(str(compare_at)) / Decimal("100")
                except InvalidOperation:
                    original = current

        availability = str(offer.get("availability", "")).lower()
        available = availability.endswith(("instock", "limitedavailability"))
        return _Variant(
            name=str(candidate.get("name") or sku or "Ergobaby product"),
            sku=sku,
            current_price=current,
            original_price=max(original, current),
            currency=str(offer.get("priceCurrency", "USD")).upper(),
            available=available,
            url=str(offer.get("url", "")),
        )

    def _select_variant(
        self, variants: list[_Variant], product_config: Product
    ) -> tuple[_Variant, tuple[str, ...]]:
        available = [variant for variant in variants if variant.available]
        if not available:
            raise AdapterError("Ergobaby page contains no available variants")

        candidates = available
        if product_config.option_strategy in {
            OptionStrategy.LOWEST_PRICE,
            OptionStrategy.SPECIFIC_OPTIONS,
        }:
            requested = self._specific_option_values(product_config)
            candidates = [
                variant
                for variant in candidates
                if all(
                    value in f"{variant.name} {variant.sku}".casefold()
                    for value in requested
                )
            ]
            if not candidates:
                raise AdapterError(
                    "No available Ergobaby variant matches configured options"
                )
        selected = min(candidates, key=lambda variant: variant.current_price)
        if product_config.option_strategy is not OptionStrategy.LOWEST_PRICE:
            return selected, ()
        ties = tuple(
            self._variant_label(variant)
            for variant in candidates
            if variant is not selected
            and variant.current_price == selected.current_price
        )
        return selected, ties

    @staticmethod
    def _variant_label(variant: _Variant) -> str:
        option_name = ErgobabyAdapter._variant_options(variant)
        return option_name.rsplit("/", maxsplit=1)[-1].strip()

    @staticmethod
    def _variant_options(variant: _Variant) -> str:
        return variant.name.rsplit(" - ", maxsplit=1)[-1].strip()

    @staticmethod
    def _specific_option_values(product_config: Product) -> list[str]:
        return [
            str(value).strip().casefold()
            for value in product_config.options.values()
            if value is not None
            and str(value).strip().casefold() not in {"", "any"}
        ]

    def _configured_url(self, product_config: Product) -> str:
        store = product_config.stores.get(self.store_name)
        return store.url if store is not None else ""

import argparse
import logging
from pathlib import Path
from typing import Sequence

from price_tracker.alerts.dry_run import DryRunNotificationReporter
from price_tracker.alerts.email import EmailAlert
from price_tracker.alerts.service import NotificationService
from price_tracker.adapters.ergobaby import ErgobabyAdapter
from price_tracker.adapters.fake import FakeAdapter, fake_transport
from price_tracker.adapters.woolino import WoolinoAdapter
from price_tracker.config.loader import ConfigError, load_catalog, load_settings
from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData
from price_tracker.services.checker import PriceChecker
from price_tracker.utils.http_client import HttpClient

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="price-tracker")
    parser.add_argument(
        "--products",
        "--config",
        dest="products",
        type=Path,
        default=Path("config/products.yaml"),
        help="Product configuration path (default: config/products.yaml)",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path("config/settings.yaml"),
        help="Application settings path (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Override the database path from settings.yaml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Check all enabled products")
    check.add_argument(
        "--dry-run-notifications",
        action="store_true",
        help="Print qualifying notifications without sending email",
    )
    subparsers.add_parser("list-products", help="List configured products")
    latest = subparsers.add_parser("latest", help="Show recent price checks")
    latest.add_argument("--limit", type=int, default=20)
    return parser


def _describe(price: PriceData) -> str:
    status = "available" if price.availability else "unavailable"
    description = (
        f"{price.product_name} | {price.store} | "
        f"{price.currency} {price.current_price} "
        f"(was {price.original_price}, {price.discount_percent}% off) | {status}"
    )
    if price.tied_variants:
        description += f" | tied lowest with: {', '.join(price.tied_variants)}"
    return description


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = load_settings(args.settings)
        catalog = load_catalog(args.products)
    except ConfigError as exc:
        LOGGER.error("%s", exc)
        return 2
    logging.getLogger().setLevel(settings.logging_level)

    if args.command == "list-products":
        for product in catalog.products:
            stores = ", ".join(product.stores)
            options = ", ".join(
                f"{key}={value}" for key, value in product.options.items()
            )
            LOGGER.info(
                "%s | %s | %s | stores: %s | strategy: %s | "
                "options: %s | threshold: %s%%",
                product.name,
                product.category,
                "enabled" if product.enabled else "disabled",
                stores,
                product.option_strategy,
                options or "none",
                catalog.threshold_for(
                    product, settings.default_notification_threshold
                ),
            )
        return 0

    storage = PriceStorage(args.database or settings.database_path)
    storage.initialize()
    if args.command == "check":
        http_client = HttpClient(transports={"fake": fake_transport})
        if args.dry_run_notifications:
            notification_service = DryRunNotificationReporter(
                storage, settings.email
            )
        elif settings.email.enabled:
            notification_service = NotificationService(
                storage, (EmailAlert(settings.email),)
            )
        else:
            notification_service = None
        results = PriceChecker(
            storage,
            {
                "ergobaby": ErgobabyAdapter(),
                "fake": FakeAdapter(),
                "woolino": WoolinoAdapter(),
            },
            http_client,
            notification_service,
            settings.default_notification_threshold,
        ).check(catalog)
        if args.dry_run_notifications:
            notification_service.report_summary()
        else:
            for result in results:
                LOGGER.info("%s", _describe(result))
        LOGGER.info("Stored %d successful price check(s)", len(results))
        return 0

    if args.limit < 1:
        LOGGER.error("--limit must be at least 1")
        return 2
    for price in storage.latest(args.limit):
        LOGGER.info("%s | %s", price.checked_at.isoformat(), _describe(price))
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(run())

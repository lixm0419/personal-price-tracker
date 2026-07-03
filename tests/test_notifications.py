from datetime import datetime, timezone
from decimal import Decimal

from price_tracker.alerts.email import EmailAlert
from price_tracker.alerts.dry_run import DryRunNotificationReporter
from price_tracker.alerts.service import NotificationService, should_notify
from price_tracker.database.storage import PriceStorage
from price_tracker.models.price import PriceData
from price_tracker.models.product import Product, StoreConfig
from price_tracker.models.settings import EmailSettings


def _price(discount: str = "20", *, available: bool = True) -> PriceData:
    return PriceData(
        product_name="Carrier - Mesh / Soft Olive",
        category="baby",
        store="ergobaby",
        original_price=Decimal("200"),
        current_price=Decimal("160"),
        discount_amount=Decimal("40"),
        discount_percent=Decimal(discount),
        currency="USD",
        availability=available,
        product_url="https://example.test/carrier?variant=1",
        checked_at=datetime.now(timezone.utc),
        tied_variants=("Natural Beige",),
        selected_variant="Mesh / Soft Olive",
    )


def test_should_notify_at_or_above_threshold() -> None:
    assert should_notify(_price("10"), Decimal("10"))
    assert should_notify(_price("20"), Decimal("10"))


def test_should_not_notify_below_threshold_unavailable_or_duplicate() -> None:
    assert not should_notify(_price("9.99"), Decimal("10"))
    assert not should_notify(
        _price("20", available=False), Decimal("10")
    )
    assert not should_notify(
        _price("20"), Decimal("10"), already_sent=True
    )


def test_notification_service_sends_once_for_unchanged_discount(tmp_path) -> None:
    class RecordingChannel:
        def __init__(self) -> None:
            self.sent: list[PriceData] = []

        def send(self, price: PriceData, product: Product) -> None:
            self.sent.append(price)

    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    channel = RecordingChannel()
    service = NotificationService(storage, (channel,))
    product = Product(
        name="Carrier",
        category="baby",
        enabled=True,
        stores={"ergobaby": StoreConfig("https://example.test/carrier")},
    )
    price = _price()

    assert service.notify(price, product, Decimal("10"))
    assert not service.notify(price, product, Decimal("10"))
    assert channel.sent == [price]


def test_email_contains_price_variant_url_and_tied_variants() -> None:
    product = Product(
        name="Carrier",
        category="baby",
        enabled=True,
        stores={"ergobaby": StoreConfig("https://example.test/carrier")},
    )
    alert = EmailAlert(
        EmailSettings(
            enabled=True,
            smtp_host="smtp.example.test",
            username="user",
            password="password",
            sender="alerts@example.test",
            recipient="shopper@example.test",
        )
    )

    body = alert._message(_price(), product).get_content()

    assert "Product: Carrier" in body
    assert "Store: ergobaby" in body
    assert "Selected variant/options: Mesh / Soft Olive" in body
    assert "Original price: USD 200" in body
    assert "Current price: USD 160" in body
    assert "Discount: 20%" in body
    assert "https://example.test/carrier?variant=1" in body
    assert "Tied lowest variants: Natural Beige" in body


def test_test_email_has_expected_subject_and_body(monkeypatch) -> None:
    alert = EmailAlert(
        EmailSettings(
            enabled=True,
            smtp_host="smtp.example.test",
            username="user",
            password="password",
            sender="alerts@example.test",
            recipient="shopper@example.test",
        )
    )
    sent = []
    monkeypatch.setattr(alert, "_send_message", sent.append)

    alert.send_test_email()

    assert len(sent) == 1
    assert sent[0]["Subject"] == "Price Tracker Test Email"
    assert "SMTP configuration is working." in sent[0].get_content()


def test_dry_run_reports_would_send_with_tied_variants(
    tmp_path, caplog, monkeypatch
) -> None:
    caplog.set_level("INFO")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    product = Product(
        name="Carrier",
        category="baby",
        enabled=True,
        stores={"ergobaby": StoreConfig("https://example.test/carrier")},
    )

    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    reporter = DryRunNotificationReporter(
        storage,
        EmailSettings(
            enabled=True,
            smtp_host="smtp.example.test",
            username_env="SMTP_USER",
            password_env="SMTP_PASSWORD",
            sender_env="SMTP_SENDER",
            recipient_env="SMTP_RECIPIENT",
            username="user",
            password="password",
            sender="alerts@example.test",
            recipient="shopper@example.test",
        ),
    )

    assert reporter.notify(_price(), product, Decimal("10"))
    reporter.report_summary()

    assert "Notification status: WOULD SEND" in caplog.text
    assert "Selected variant/options: Mesh / Soft Olive" in caplog.text
    assert "Tied lowest variants: Natural Beige" in caplog.text
    assert "Checked: 1" in caplog.text
    assert "Would notify: 1" in caplog.text
    assert "Skipped: 0" in caplog.text


def test_dry_run_reports_skip_reasons_without_empty_ties(
    tmp_path, caplog
) -> None:
    caplog.set_level("INFO")
    product = Product(
        name="Carrier",
        category="baby",
        enabled=True,
        stores={"ergobaby": StoreConfig("https://example.test/carrier")},
    )
    storage = PriceStorage(tmp_path / "prices.db")
    storage.initialize()
    reporter = DryRunNotificationReporter(storage, EmailSettings())

    assert not reporter.notify(_price("5"), product, Decimal("10"))
    assert not reporter.notify(
        _price("20", available=False), product, Decimal("10")
    )

    assert "Reason: Discount below threshold" in caplog.text
    assert "Reason: Product unavailable" in caplog.text
    assert "Tied lowest variants" not in caplog.text

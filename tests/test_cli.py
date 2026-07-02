import logging
from datetime import datetime, timezone
from decimal import Decimal

from price_tracker.cli import _describe, run
from price_tracker.models.price import PriceData


def _config(tmp_path):
    path = tmp_path / "products.yaml"
    path.write_text(
        """
products:
  - name: Test Item
    category: test
    enabled: true
    option_strategy: all_options
    options:
      flavor: any
    stores:
      fake:
        url: fake://item?original=100&current=75
""",
        encoding="utf-8",
    )
    return path


def _settings(tmp_path, database, *, email_enabled=False):
    path = tmp_path / "settings.yaml"
    path.write_text(
        f"""
default_notification_threshold: 12
database_path: {database.as_posix()}
logging_level: INFO
email:
  enabled: {str(email_enabled).lower()}
  smtp_host: smtp.example.test
  sender: alerts@example.test
  recipient: shopper@example.test
""",
        encoding="utf-8",
    )
    return path


def test_cli_commands(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    config = _config(tmp_path)
    database = tmp_path / "prices.db"
    settings = _settings(tmp_path, database)
    common = ["--products", str(config), "--settings", str(settings)]

    assert run([*common, "list-products"]) == 0
    assert "Test Item" in caplog.text
    assert "strategy: all_options" in caplog.text
    assert "flavor=any" in caplog.text
    caplog.clear()

    assert run([*common, "check"]) == 0
    assert "Stored 1 successful price check(s)" in caplog.text
    caplog.clear()

    assert run([*common, "latest", "--limit", "1"]) == 0
    assert "25.00% off" in caplog.text


def test_cli_database_override_wins_over_settings(tmp_path):
    config = _config(tmp_path)
    configured_database = tmp_path / "configured.db"
    override_database = tmp_path / "override.db"
    settings = _settings(tmp_path, configured_database)
    assert (
        run(
            [
                "--products",
                str(config),
                "--settings",
                str(settings),
                "--database",
                str(override_database),
                "check",
            ]
        )
        == 0
    )
    assert override_database.exists()
    assert not configured_database.exists()


def _price_data(tied_variants: tuple[str, ...] = ()) -> PriceData:
    return PriceData(
        product_name="Omni Deluxe Baby Carrier - Mesh / Soft Olive",
        category="baby",
        store="ergobaby",
        original_price=Decimal("159"),
        current_price=Decimal("159"),
        discount_amount=Decimal("0"),
        discount_percent=Decimal("0"),
        currency="USD",
        availability=True,
        product_url="https://example.test/product",
        checked_at=datetime.now(timezone.utc),
        tied_variants=tied_variants,
    )


def test_cli_description_is_unchanged_without_ties():
    description = _describe(_price_data())

    assert description.endswith("0% off) | available")
    assert "tied lowest" not in description


def test_cli_description_displays_tied_variants():
    description = _describe(_price_data(("Natural Beige", "Onyx Black")))

    assert description.endswith(
        "tied lowest with: Natural Beige, Onyx Black"
    )


def test_check_dry_run_prints_complete_report(
    tmp_path, caplog, monkeypatch
):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("PRICE_TRACKER_EMAIL_USERNAME", "user")
    monkeypatch.setenv("PRICE_TRACKER_EMAIL_PASSWORD", "password")
    config = _config(tmp_path)
    database = tmp_path / "dry-run.db"
    settings = _settings(tmp_path, database, email_enabled=True)

    assert (
        run(
            [
                "--products",
                str(config),
                "--settings",
                str(settings),
                "check",
                "--dry-run-notifications",
            ]
        )
        == 0
    )

    assert "Product: Test Item" in caplog.text
    assert "Store: fake" in caplog.text
    assert "Selected variant/options: Not specified" in caplog.text
    assert "Original price: USD 100" in caplog.text
    assert "Current price: USD 75" in caplog.text
    assert "Discount: 25.00%" in caplog.text
    assert "Notification status: WOULD SEND" in caplog.text
    assert "Product URL: fake://item?original=100&current=75" in caplog.text
    assert "Tied lowest variants" not in caplog.text
    assert "Notification Summary" in caplog.text
    assert "Checked: 1" in caplog.text
    assert "Would notify: 1" in caplog.text
    assert "Skipped: 0" in caplog.text

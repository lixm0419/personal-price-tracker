from decimal import Decimal

import pytest

from price_tracker.config.loader import ConfigError, load_catalog, load_settings
from price_tracker.models.product import OptionStrategy


def test_load_catalog_keeps_optional_threshold_override(tmp_path):
    path = tmp_path / "products.yaml"
    path.write_text(
        """
products:
  - name: One
    category: toys
    enabled: true
    options:
      color: any
      sku: 1234
    stores:
      fake:
        url: fake://one?original=10&current=8
  - name: Two
    enabled: false
    notification_threshold: 20
    option_strategy: specific_options
    stores:
      fake:
        url: fake://two?original=10&current=7
""",
        encoding="utf-8",
    )
    catalog = load_catalog(path)
    assert catalog.products[0].notification_threshold is None
    assert catalog.products[0].option_strategy is OptionStrategy.LOWEST_PRICE
    assert catalog.products[0].options == {"color": "any", "sku": 1234}
    assert catalog.products[0].stores["fake"].url.startswith("fake://one")
    assert catalog.products[1].notification_threshold == Decimal("20")
    assert (
        catalog.products[1].option_strategy
        is OptionStrategy.SPECIFIC_OPTIONS
    )
    assert catalog.products[1].category == "uncategorized"
    assert len(catalog.enabled_products) == 1


def test_load_catalog_rejects_missing_stores(tmp_path):
    path = tmp_path / "products.yaml"
    path.write_text("products:\n  - name: Broken\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="stores"):
        load_catalog(path)


def test_load_catalog_rejects_unknown_option_strategy(tmp_path):
    path = tmp_path / "products.yaml"
    path.write_text(
        """
products:
  - name: Broken
    option_strategy: cheapest_blue_one
    stores:
      fake:
        url: fake://broken?original=10&current=8
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="option_strategy"):
        load_catalog(path)


def test_load_settings_with_email_environment_names(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("SMTP_SENDER", "alerts@example.test")
    monkeypatch.setenv("SMTP_RECIPIENT", "shopper@example.test")
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
database_path: custom/prices.db
logging_level: debug
email:
  enabled: true
  smtp_host: smtp.example.com
  username_env: SMTP_USER
  password_env: SMTP_PASSWORD
  sender_env: SMTP_SENDER
  recipient_env: SMTP_RECIPIENT
""",
        encoding="utf-8",
    )
    settings = load_settings(path)
    assert settings.default_notification_threshold == Decimal("10")
    assert settings.database_path.as_posix() == "custom/prices.db"
    assert settings.logging_level == "DEBUG"
    assert settings.email.smtp_host == "smtp.example.com"
    assert settings.email.smtp_port == 587
    assert settings.email.username_env == "SMTP_USER"
    assert settings.email.password_env == "SMTP_PASSWORD"
    assert settings.email.sender_env == "SMTP_SENDER"
    assert settings.email.recipient_env == "SMTP_RECIPIENT"
    assert settings.email.username == "user"
    assert settings.email.password == "password"
    assert settings.email.sender == "alerts@example.test"
    assert settings.email.recipient == "shopper@example.test"


def test_load_settings_names_exact_missing_environment_variable(
    tmp_path, monkeypatch
):
    for name in (
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_SENDER",
        "SMTP_RECIPIENT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("SMTP_SENDER", "alerts@example.test")
    path = tmp_path / "settings.yaml"
    path.write_text(
        """
email:
  enabled: true
  smtp_host: smtp.example.test
  username_env: SMTP_USER
  password_env: SMTP_PASSWORD
  sender_env: SMTP_SENDER
  recipient_env: SMTP_RECIPIENT
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="Missing environment variable:\\nSMTP_RECIPIENT",
    ):
        load_settings(path)


def test_load_settings_rejects_invalid_logging_level(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("logging_level: noisy\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="logging_level"):
        load_settings(path)

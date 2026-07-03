import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from price_tracker.models.product import (
    OptionStrategy,
    OptionValue,
    Product,
    ProductCatalog,
    StoreConfig,
)
from price_tracker.models.settings import ApplicationSettings, EmailSettings

DEFAULT_NOTIFICATION_THRESHOLD = Decimal("10")
DEFAULT_DATABASE_PATH = Path("data/prices.db")
DEFAULT_LOGGING_LEVEL = "INFO"
VALID_LOGGING_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


class ConfigError(ValueError):
    """Raised when application configuration is invalid."""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in configuration: {path}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Configuration root must be a mapping: {path}")
    return raw


def _threshold(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ConfigError(f"{field} must be a number") from exc
    if not Decimal("0") <= result <= Decimal("100"):
        raise ConfigError(f"{field} must be between 0 and 100")
    return result


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a non-empty string or null")
    return value.strip()


def _load_email(raw: Any) -> EmailSettings:
    if raw is None:
        return EmailSettings()
    if not isinstance(raw, dict):
        raise ConfigError("email must be a mapping")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("email.enabled must be true or false")
    port = raw.get("smtp_port", 587)
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ConfigError("email.smtp_port must be an integer between 1 and 65535")
    use_tls = raw.get("use_tls", True)
    if not isinstance(use_tls, bool):
        raise ConfigError("email.use_tls must be true or false")
    smtp_host = _optional_string(raw.get("smtp_host"), "email.smtp_host")
    if enabled and smtp_host is None:
        raise ConfigError("email.smtp_host is required when email is enabled")
    environment_names = {
        "username": (
            _optional_string(raw.get("username_env"), "email.username_env")
            or "PRICE_TRACKER_EMAIL_USERNAME"
        ),
        "password": (
            _optional_string(raw.get("password_env"), "email.password_env")
            or "PRICE_TRACKER_EMAIL_PASSWORD"
        ),
        "sender": (
            _optional_string(raw.get("sender_env"), "email.sender_env")
            or "PRICE_TRACKER_EMAIL_SENDER"
        ),
        "recipient": (
            _optional_string(raw.get("recipient_env"), "email.recipient_env")
            or "PRICE_TRACKER_EMAIL_RECIPIENT"
        ),
    }
    resolved = {
        field: os.environ.get(variable)
        for field, variable in environment_names.items()
    }
    if enabled:
        for field in ("username", "password", "sender", "recipient"):
            if not resolved[field]:
                raise ConfigError(
                    "Missing environment variable:\n"
                    f"{environment_names[field]}"
                )
    return EmailSettings(
        enabled=enabled,
        smtp_host=smtp_host,
        smtp_port=port,
        username_env=environment_names["username"],
        password_env=environment_names["password"],
        sender_env=environment_names["sender"],
        recipient_env=environment_names["recipient"],
        use_tls=use_tls,
        username=resolved["username"],
        password=resolved["password"],
        sender=resolved["sender"],
        recipient=resolved["recipient"],
    )


def load_settings(path: Path) -> ApplicationSettings:
    raw = _load_yaml(path)
    database_path = raw.get("database_path", str(DEFAULT_DATABASE_PATH))
    if not isinstance(database_path, str) or not database_path.strip():
        raise ConfigError("database_path must be a non-empty string")
    logging_level = raw.get("logging_level", DEFAULT_LOGGING_LEVEL)
    if not isinstance(logging_level, str):
        raise ConfigError("logging_level must be a string")
    logging_level = logging_level.upper()
    if logging_level not in VALID_LOGGING_LEVELS:
        raise ConfigError(
            "logging_level must be one of: " + ", ".join(sorted(VALID_LOGGING_LEVELS))
        )
    return ApplicationSettings(
        default_notification_threshold=_threshold(
            raw.get(
                "default_notification_threshold", DEFAULT_NOTIFICATION_THRESHOLD
            ),
            "default_notification_threshold",
        ),
        database_path=Path(database_path),
        logging_level=logging_level,
        email=_load_email(raw.get("email")),
    )


def _product(raw: Any, index: int) -> Product:
    if not isinstance(raw, dict):
        raise ConfigError(f"products[{index}] must be a mapping")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"products[{index}].name must be a non-empty string")
    category = raw.get("category", "uncategorized")
    if not isinstance(category, str) or not category.strip():
        raise ConfigError(f"products[{index}].category must be a non-empty string")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"products[{index}].enabled must be true or false")
    stores_raw = raw.get("stores")
    if not isinstance(stores_raw, dict) or not stores_raw:
        raise ConfigError(f"products[{index}].stores must be a non-empty mapping")
    stores: dict[str, StoreConfig] = {}
    for store, store_raw in stores_raw.items():
        field = f"products[{index}].stores"
        if not isinstance(store, str) or not store.strip():
            raise ConfigError(f"{field} keys must be non-empty store names")
        if not isinstance(store_raw, dict):
            raise ConfigError(f"{field}.{store} must be a mapping")
        url = store_raw.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ConfigError(f"{field}.{store}.url must be a non-empty string")
        stores[store.strip()] = StoreConfig(url=url.strip())
    strategy_raw = raw.get("option_strategy", OptionStrategy.LOWEST_PRICE)
    try:
        strategy = OptionStrategy(strategy_raw)
    except (ValueError, TypeError) as exc:
        supported = ", ".join(strategy.value for strategy in OptionStrategy)
        raise ConfigError(
            f"products[{index}].option_strategy must be one of: {supported}"
        ) from exc
    options_raw = raw.get("options", {})
    if not isinstance(options_raw, dict):
        raise ConfigError(f"products[{index}].options must be a mapping")
    options: dict[str, OptionValue] = {}
    for key, value in options_raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigError(
                f"products[{index}].options keys must be non-empty strings"
            )
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ConfigError(
                f"products[{index}].options.{key} must be a scalar value"
            )
        options[key.strip()] = value
    threshold_value = raw.get("notification_threshold")
    threshold = (
        _threshold(threshold_value, f"products[{index}].notification_threshold")
        if threshold_value is not None
        else None
    )
    return Product(
        name=name.strip(),
        category=category.strip(),
        enabled=enabled,
        stores=stores,
        notification_threshold=threshold,
        option_strategy=strategy,
        options=options,
    )


def load_catalog(path: Path) -> ProductCatalog:
    raw = _load_yaml(path)
    products = raw.get("products")
    if not isinstance(products, list):
        raise ConfigError("products must be a list")
    return ProductCatalog(
        products=tuple(_product(item, index) for index, item in enumerate(products))
    )

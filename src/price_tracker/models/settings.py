from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EmailSettings:
    enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    username_env: str = "PRICE_TRACKER_EMAIL_USERNAME"
    password_env: str = "PRICE_TRACKER_EMAIL_PASSWORD"
    sender: str | None = None
    recipient: str | None = None
    use_tls: bool = True


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    default_notification_threshold: Decimal
    database_path: Path
    logging_level: str
    email: EmailSettings

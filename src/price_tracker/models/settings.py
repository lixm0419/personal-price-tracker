from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EmailSettings:
    enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    username_env: str = "PRICE_TRACKER_EMAIL_USERNAME"
    password_env: str = "PRICE_TRACKER_EMAIL_PASSWORD"
    sender_env: str = "PRICE_TRACKER_EMAIL_SENDER"
    recipient_env: str = "PRICE_TRACKER_EMAIL_RECIPIENT"
    use_tls: bool = True
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    sender: str | None = field(default=None, repr=False)
    recipient: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    default_notification_threshold: Decimal
    database_path: Path
    logging_level: str
    email: EmailSettings

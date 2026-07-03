import smtplib
from email.message import EmailMessage

from price_tracker.alerts.formatting import format_notification
from price_tracker.models.price import PriceData
from price_tracker.models.product import Product
from price_tracker.models.settings import EmailSettings


class EmailConfigurationError(RuntimeError):
    """Email is enabled but its environment credentials are unavailable."""


class EmailAlert:
    def __init__(self, settings: EmailSettings) -> None:
        self.settings = settings

    def send(self, price: PriceData, product: Product) -> None:
        self._send_message(self._message(price, product))

    def send_test_email(self) -> None:
        message = EmailMessage()
        message["Subject"] = "Price Tracker Test Email"
        message["From"] = self.settings.sender
        message["To"] = self.settings.recipient
        message.set_content("SMTP configuration is working.")
        self._send_message(message)

    def _send_message(self, message: EmailMessage) -> None:
        if not all(
            (
                self.settings.smtp_host,
                self.settings.username,
                self.settings.password,
                self.settings.sender,
                self.settings.recipient,
            )
        ):
            raise EmailConfigurationError("Email settings are incomplete")

        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=30
        ) as smtp:
            if self.settings.use_tls:
                smtp.starttls()
            smtp.login(self.settings.username, self.settings.password)
            smtp.send_message(message)

    def _message(self, price: PriceData, product: Product) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = (
            f"Price alert: {product.name} is {price.discount_percent}% off"
        )
        message["From"] = self.settings.sender
        message["To"] = self.settings.recipient
        message.set_content(format_notification(price, product))
        return message

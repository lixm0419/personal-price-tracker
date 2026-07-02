import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from price_tracker.models.price import PriceData


class PriceStorage:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS price_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checked_at TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    store TEXT NOT NULL,
                    original_price TEXT NOT NULL,
                    current_price TEXT NOT NULL,
                    discount_amount TEXT NOT NULL,
                    discount_percent TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    availability INTEGER NOT NULL,
                    product_url TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_history "
                "ON price_checks(product_name, store, checked_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_notifications (
                    product_name TEXT NOT NULL,
                    store TEXT NOT NULL,
                    product_url TEXT NOT NULL,
                    discount_percent TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    PRIMARY KEY (
                        product_name, store, product_url, discount_percent
                    )
                )
                """
            )

    def save(self, price: PriceData) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO price_checks (
                    checked_at, product_name, category, store, original_price,
                    current_price, discount_amount, discount_percent, currency,
                    availability, product_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    price.checked_at.isoformat(),
                    price.product_name,
                    price.category,
                    price.store,
                    str(price.original_price),
                    str(price.current_price),
                    str(price.discount_amount),
                    str(price.discount_percent),
                    price.currency,
                    int(price.availability),
                    price.product_url,
                ),
            )

    def latest(self, limit: int = 20) -> list[PriceData]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT product_name, category, store, original_price,
                       current_price, discount_amount, discount_percent,
                       currency, availability, product_url, checked_at
                FROM price_checks
                ORDER BY checked_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PriceData(
                product_name=row[0],
                category=row[1],
                store=row[2],
                original_price=Decimal(row[3]),
                current_price=Decimal(row[4]),
                discount_amount=Decimal(row[5]),
                discount_percent=Decimal(row[6]),
                currency=row[7],
                availability=bool(row[8]),
                product_url=row[9],
                checked_at=datetime.fromisoformat(row[10]),
            )
            for row in rows
        ]

    def notification_was_sent(self, price: PriceData) -> bool:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM sent_notifications
                WHERE product_name = ?
                  AND store = ?
                  AND product_url = ?
                  AND discount_percent = ?
                """,
                (
                    price.product_name,
                    price.store,
                    price.product_url,
                    str(price.discount_percent),
                ),
            ).fetchone()
        return row is not None

    def record_notification(self, price: PriceData) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sent_notifications (
                    product_name, store, product_url, discount_percent, sent_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    price.product_name,
                    price.store,
                    price.product_url,
                    str(price.discount_percent),
                    datetime.now().astimezone().isoformat(),
                ),
            )

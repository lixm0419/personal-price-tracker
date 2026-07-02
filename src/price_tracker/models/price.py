from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PriceData:
    product_name: str
    category: str
    store: str
    original_price: Decimal
    current_price: Decimal
    discount_amount: Decimal
    discount_percent: Decimal
    currency: str
    availability: bool
    product_url: str
    checked_at: datetime
    tied_variants: tuple[str, ...] = ()
    selected_variant: str | None = None

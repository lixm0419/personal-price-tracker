from decimal import Decimal, ROUND_HALF_UP

MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.01")


def calculate_discount(
    original_price: Decimal, current_price: Decimal
) -> tuple[Decimal, Decimal]:
    if original_price < 0 or current_price < 0:
        raise ValueError("Prices cannot be negative")
    if original_price == 0:
        return Decimal("0.00"), Decimal("0.00")
    amount = max(original_price - current_price, Decimal("0"))
    percent = amount / original_price * Decimal("100")
    return (
        amount.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP),
        percent.quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP),
    )


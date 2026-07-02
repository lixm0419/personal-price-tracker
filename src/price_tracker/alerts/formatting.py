from price_tracker.models.price import PriceData
from price_tracker.models.product import Product


def format_notification(price: PriceData, product: Product) -> str:
    tied = ", ".join(price.tied_variants) if price.tied_variants else "None"
    return "\n".join(
        (
            f"Product: {product.name}",
            f"Store: {price.store}",
            "Selected variant/options: "
            f"{price.selected_variant or 'Not specified'}",
            f"Original price: {price.currency} {price.original_price}",
            f"Current price: {price.currency} {price.current_price}",
            f"Discount: {price.discount_percent}%",
            f"Product URL: {price.product_url}",
            f"Tied lowest variants: {tied}",
        )
    )

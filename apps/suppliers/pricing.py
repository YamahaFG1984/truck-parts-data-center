"""Cost comparison and suggested selling price (DESIGN.md §6, ADR-08: prices never come from AI)."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings


def to_usd(amount: Decimal, currency: str) -> Decimal:
    rate = Decimal(str(settings.FX_TO_USD.get(currency, 1)))
    return (Decimal(amount) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def price_product(product, offers=None) -> dict:
    """Offers sorted by USD cost plus the suggested price derived from the best fresh offer."""
    offers = list(product.offers.all()) if offers is None else list(offers)
    fresh_after = date.today() - timedelta(days=settings.OFFER_FRESH_DAYS)
    rows = sorted(
        (
            {
                "offer": o,
                "supplier": o.supplier,
                "cost_usd": to_usd(o.cost_price, o.currency),
                "fresh": o.quoted_at >= fresh_after,
            }
            for o in offers
        ),
        key=lambda r: (not r["fresh"], r["cost_usd"]),
    )
    best = rows[0] if rows else None
    suggested = None
    if best:
        margin = Decimal(str(product.category.margin_rate))
        suggested = (best["cost_usd"] * (1 + margin)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "offers": rows,
        "best": best,
        "suggested_price_usd": suggested,
        "stale": bool(best and not best["fresh"]),
        "margin_rate": product.category.margin_rate,
    }

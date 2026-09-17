from decimal import Decimal

from apps.suppliers.pricing import price_product, to_usd


def test_to_usd(settings):
    settings.FX_TO_USD = {"CNY": 0.14, "USD": 1}
    assert to_usd(Decimal("100"), "CNY") == Decimal("14.00")


def test_fresh_offer_preferred_over_cheaper_stale_one(catalog, settings):
    settings.FX_TO_USD = {"CNY": 0.14, "USD": 1}
    pricing = price_product(catalog["pad"])
    assert pricing["best"]["cost_usd"] == Decimal("14.00")  # 100 CNY fresh, not 50 CNY from 400 days ago
    assert pricing["suggested_price_usd"] == Decimal("18.20")  # 14 * 1.30
    assert not pricing["stale"]


def test_no_offer(catalog):
    pricing = price_product(catalog["spring"])
    assert pricing["best"] is None and pricing["suggested_price_usd"] is None

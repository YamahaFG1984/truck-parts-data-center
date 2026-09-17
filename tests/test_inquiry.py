from decimal import Decimal

from apps.ai import mock
from apps.inquiry import services
from apps.inquiry.models import Inquiry

EMAIL = """Dear Sales,
Please quote:
1. OE 81.50804-6004 x 20
2. 20837192 qty 10
3. Rear axle air spring for Volvo FH4, 6 pcs

Best regards,
Erik
Nordic Fleet Service AB"""


def test_mock_parser_splits_lines():
    parsed = mock.parse_inquiry({"text": EMAIL})
    assert parsed["customer"] == "Nordic Fleet Service AB"
    assert [(l["part_no"], l["qty"]) for l in parsed["lines"]] == [("81.50804-6004", 20), ("20837192", 10), (None, 6)]
    assert parsed["lines"][2]["vehicle"] == "Volvo"


def test_run_inquiry_end_to_end(catalog, settings):
    settings.FX_TO_USD = {"CNY": 0.14, "USD": 1}
    inquiry = services.run_inquiry(Inquiry.objects.create(raw_text=EMAIL))
    lines = list(inquiry.lines.all())
    assert inquiry.customer == "Nordic Fleet Service AB"
    assert lines[0].selected_product_id == catalog["pad"].id and lines[0].unit_price_usd == Decimal("18.20")
    assert lines[1].selected_product_id == catalog["pad2"].id  # fuzzy >= 80 auto-selected
    assert lines[2].selected_product_id is None  # semantic stays a suggestion
    assert lines[2].candidates[0]["product_id"] == catalog["spring"].id

    text, warnings = services.generate_quote_email(inquiry)
    assert "USD 18.20" in text and "USD 364.00" in text and warnings == []

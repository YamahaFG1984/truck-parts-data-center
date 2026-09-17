"""Listing copy generation with platform checks (PRD §6.4)."""

import csv
import io
import re

from apps.ai import client as ai
from apps.ai.schemas import ListingDraft
from apps.catalog.services import product_payload
from apps.core.utils import normalize_part_no

from .models import ListingContent

TITLE_LIMIT = {"alibaba": 128, "shopify": 70}
NUMBER_TOKEN = re.compile(r"\b[A-Z]{0,3}\s?\d[\d\s.\-/]{3,}\d\b")


def validate(listing: ListingContent) -> list[str]:
    warnings = []
    limit = TITLE_LIMIT[listing.platform]
    if len(listing.title) > limit:
        warnings.append(f"标题 {len(listing.title)} 字符，超过 {listing.get_platform_display()} 限制 {limit}")
    if listing.platform == "alibaba" and len(listing.keywords) != 3:
        warnings.append(f"Alibaba 需要 3 个关键词，当前 {len(listing.keywords)} 个")
    known = {pn.normalized for pn in listing.product.part_numbers.all()}
    text = " ".join([listing.title, listing.description, *listing.bullets, *listing.keywords, *(f"{f['q']} {f['a']}" for f in listing.faq)])
    unknown = sorted({m.strip() for m in NUMBER_TOKEN.findall(text) if len(normalize_part_no(m)) >= 5 and normalize_part_no(m) not in known})
    # Spec values such as "430 mm" also look numeric; only warn on tokens that resemble part numbers.
    unknown = [u for u in unknown if sum(c.isdigit() for c in u) >= 5]
    if unknown:
        warnings.append(f"文案中出现产品库里不存在的号码：{', '.join(unknown)}（可能是 AI 编造，请核实）")
    return warnings


def generate(product, platform: str) -> ListingContent:
    draft = ai.chat_json(f"listing_{platform}", f"listing_{platform}", {"product": product_payload(product)}, ListingDraft)
    listing = ListingContent(
        product=product, platform=platform, title=draft.title[:300], keywords=draft.keywords, bullets=draft.bullets,
        description=draft.description, faq=[f.model_dump() for f in draft.faq],
    )
    listing.warnings = validate(listing)
    listing.save()
    return listing


def shopify_csv(listings) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type", "Tags", "Published", "Variant SKU", "Variant Weight Unit", "Variant Grams", "Image Src"])
    for listing in listings:
        p = listing.product
        body = "<ul>" + "".join(f"<li>{b}</li>" for b in listing.bullets) + f"</ul><p>{listing.description}</p>"
        body += "".join(f"<p><strong>{f['q']}</strong><br>{f['a']}</p>" for f in listing.faq)
        image = p.primary_image
        writer.writerow([
            p.sku.lower(), listing.title, body, "FIT Truck Parts", "Vehicles & Parts > Vehicle Parts & Accessories",
            p.category.name_en, ", ".join(listing.keywords), "TRUE", p.sku, "kg",
            int(p.weight_kg * 1000) if p.weight_kg else "", image.image.url if image else "",
        ])
    return buffer.getvalue()

"""Inquiry workflow: parse -> match -> price -> quote (PRD §6.1)."""

import re
import time
from decimal import Decimal

from apps.ai import client as ai
from apps.ai import mock
from apps.ai.schemas import ImageIdentification, ParsedInquiry
from apps.catalog.services import product_detail_queryset
from apps.suppliers.pricing import price_product

from . import matching
from .models import Inquiry, InquiryLine

AUTO_SELECT_SCORE = 80
IMAGE_WEIGHT = 0.9


def run_inquiry(inquiry: Inquiry) -> Inquiry:
    started = time.monotonic()
    requests = []  # (part_no, description, qty, vehicle, weight, label)
    if inquiry.image:
        ident = ai.vision_json("inquiry_image", "image_identify", inquiry.image.path, ImageIdentification)
        inquiry.image_result = ident.model_dump()
        label = f"[图片] {ident.part_type_cn or ident.part_type}"
        for number in ident.visible_numbers:
            requests.append((number, ident.description, 1, None, IMAGE_WEIGHT, f"{label} {number}"))
        if not ident.visible_numbers:
            requests.append((None, ident.description or ident.part_type, 1, None, IMAGE_WEIGHT, label))
    if inquiry.raw_text.strip():
        parsed = ai.chat_json("inquiry_parse", "parse_inquiry", {"text": inquiry.raw_text}, ParsedInquiry)
        if parsed.customer and not inquiry.customer:
            inquiry.customer = " ".join(parsed.customer.split())[:100]
        for line in parsed.lines:
            label = " · ".join(filter(None, [line.part_no, line.description, line.vehicle]))
            requests.append((line.part_no, line.description, max(line.qty, 1), line.vehicle, 1.0, label))

    inquiry.save()
    inquiry.lines.all().delete()
    for position, (part_no, description, qty, vehicle, weight, label) in enumerate(requests):
        candidates = matching.match_line(part_no, description, vehicle, weight=weight)
        top = candidates[0] if candidates and candidates[0].score >= AUTO_SELECT_SCORE else None
        line = InquiryLine.objects.create(
            inquiry=inquiry, position=position, query=label[:500],
            parsed={"part_no": part_no, "description": description, "vehicle": vehicle},
            candidates=[c.as_dict() for c in candidates], qty=qty,
            selected_product_id=top.product_id if top else None,
        )
        update_line_price(line)
    inquiry.elapsed_ms = int((time.monotonic() - started) * 1000)
    inquiry.save(update_fields=["elapsed_ms", "customer", "image_result", "updated_at"])
    return inquiry


def update_line_price(line: InquiryLine) -> None:
    price = None
    if line.selected_product_id:
        product = product_detail_queryset().get(pk=line.selected_product_id)
        price = price_product(product)["suggested_price_usd"]
    line.unit_price_usd = price
    line.save(update_fields=["selected_product", "qty", "unit_price_usd"])


def hydrate_lines(inquiry: Inquiry) -> list[dict]:
    """Attach product objects and live pricing to the candidate snapshots for rendering."""
    lines = list(inquiry.lines.all())
    ids = {c["product_id"] for line in lines for c in line.candidates}
    products = {p.id: p for p in product_detail_queryset().filter(id__in=ids)}
    result = []
    for line in lines:
        candidates = []
        for c in line.candidates:
            product = products.get(c["product_id"])
            if product:
                candidates.append({**c, "product": product, "pricing": price_product(product)})
        result.append({"line": line, "candidates": candidates})
    return result


def quote_items(inquiry: Inquiry) -> list[dict]:
    items = []
    for row in hydrate_lines(inquiry):
        line = row["line"]
        chosen = next((c for c in row["candidates"] if c["product_id"] == line.selected_product_id), None)
        if not chosen or line.unit_price_usd is None:
            continue
        best = chosen["pricing"]["best"]
        items.append({
            "sku": chosen["product"].sku,
            "requested": line.parsed.get("part_no") or line.parsed.get("description") or "",
            "name": chosen["product"].name_en or chosen["product"].category.name_en,
            "qty": line.qty,
            "unit_price": str(line.unit_price_usd),
            "subtotal": str((line.unit_price_usd * line.qty).quantize(Decimal("0.01"))),
            "method": chosen["method"],
            "lead_time_days": best["offer"].lead_time_days if best else None,
            "moq": best["offer"].moq if best else None,
        })
    return items


def generate_quote_email(inquiry: Inquiry) -> tuple[str, list[str]]:
    items = quote_items(inquiry)
    if not items:
        return "", ["请先为至少一行选择有报价的产品"]
    total = str(sum(Decimal(i["subtotal"]) for i in items))
    variables = {"customer": inquiry.customer or "Customer", "items": items, "total": total}
    warnings = []
    try:
        text = ai.chat_text("inquiry_quote_email", "quote_email", variables)
    except ai.AIError as exc:
        text, warnings = "", [f"AI 生成失败，已使用模板：{exc}"]
    # ADR-08: the email must carry exactly the prices we calculated.
    found = set(re.findall(r"\d+\.\d{2}", text.replace(",", "")))
    missing = [i["unit_price"] for i in items if i["unit_price"] not in found]
    if not text or missing:
        if text:
            warnings.append(f"AI 邮件中价格与系统计算不一致（缺少 {', '.join(missing)}），已改用模板邮件")
        text = mock.quote_email(variables)
    inquiry.quote_email = text
    inquiry.save(update_fields=["quote_email", "updated_at"])
    return text, warnings

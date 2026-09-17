"""Column mapping + deterministic row transformation (DESIGN.md §9 steps 2-4, ADR-10)."""

import re

from apps.ai import client as ai
from apps.ai.schemas import ColumnMapping, ExtractedRow, ExtractedRows
from apps.catalog.models import Brand, PartNumber
from apps.core.utils import normalize_part_no, split_numbers
from apps.inquiry import matching

STANDARD_FIELDS = set(ExtractedRow.model_fields)
AUTO_APPROVE_SCORE = 95


def map_columns(headers: list[str], rows: list[dict]) -> dict[str, str]:
    samples = [{h: (str(v) if v is not None else None) for h, v in row.items()} for row in rows[:5]]
    result = ai.chat_json("ingest_map_columns", "map_columns", {"headers": headers, "samples": samples}, ColumnMapping)
    return {h: f for h, f in result.mapping.items() if f in STANDARD_FIELDS and h in headers}


def infer_currency(mapping: dict[str, str]) -> str:
    price_header = next((h for h, f in mapping.items() if f == "cost_price"), "")
    upper = price_header.upper()
    if "USD" in upper or "$" in upper:
        return "USD"
    if "EUR" in upper or "€" in upper:
        return "EUR"
    return "CNY"


def _number(value, cast=float):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return cast(value)
    m = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return cast(float(m.group())) if m else None


def transform_row(raw: dict, mapping: dict[str, str], default_currency: str) -> tuple[dict, list[str]]:
    data: dict = {}
    errors: list[str] = []
    for header, field in mapping.items():
        value = raw.get(header)
        if value is None:
            continue
        if field in ("oe_numbers", "cross_numbers"):
            data.setdefault(field, []).extend(split_numbers(value))
        elif field == "specs":
            data.setdefault("specs", {})[header] = str(value)
        elif field in ("cost_price", "weight_kg"):
            data[field] = _number(value)
        elif field in ("moq", "lead_time_days"):
            data[field] = _number(value, int)
        else:
            data[field] = str(value).strip()
    data.setdefault("currency", default_currency)
    data["currency"] = {"RMB": "CNY", "元": "CNY", "$": "USD"}.get(str(data["currency"]).upper(), str(data["currency"]).upper())
    row = ExtractedRow.model_validate(data).model_dump()

    if not row["cost_price"]:
        errors.append("缺少单价")
    if not (row["oe_numbers"] or row["cross_numbers"] or row["supplier_part_no"]):
        errors.append("没有任何可匹配的号码")
    return row, errors


def match_row(row: dict) -> matching.Candidate | None:
    best: matching.Candidate | None = None

    def consider(candidates):
        nonlocal best
        for c in candidates:
            if best is None or c.score > best.score:
                best = c

    if row.get("supplier_part_no"):
        hit = PartNumber.objects.filter(type=PartNumber.SUPPLIER, normalized=normalize_part_no(row["supplier_part_no"])).first()
        if hit:
            consider([matching.Candidate(hit.product_id, 100, matching.EXACT, hit.number, PartNumber.SUPPLIER)])
    for number in row.get("oe_numbers", []) + row.get("cross_numbers", []):
        if best and best.score == 100:
            break
        consider(matching.match_number(number))
    if best is None and row.get("name"):
        consider(matching.match_text(" ".join(filter(None, [row.get("name"), row.get("vehicle")])))[:1])
    return best


def split_brand(raw: str) -> tuple[Brand | None, str]:
    """"KNORR K833444" -> (Knorr-Bremse, "K833444")."""
    stripped = matching.strip_brand_prefix(raw)
    if stripped == raw:
        return None, raw
    word = raw.split()[0].lower()
    for brand in Brand.objects.all():
        n = brand.name.lower()
        if word == n or word == n.split("-")[0] or n.startswith(word):
            return brand, stripped
    return None, stripped


def extract_pdf_text(chunk: str) -> list[dict]:
    result = ai.chat_json("ingest_extract_pdf", "extract_pdf_rows", {"text": chunk}, ExtractedRows)
    return [r.model_dump() for r in result.rows]

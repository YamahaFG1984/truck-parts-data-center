"""Deterministic stand-ins for every AI capability (DESIGN.md §8.2).

They make the whole demo work offline. They are intentionally simple and rule
based: good enough to show the workflow, not a replacement for a real model.
"""

import hashlib
import json
import math
import re

from rapidfuzz import fuzz, process

from apps.core.utils import normalize_part_no

TRUCK_MAKES = ["Volvo", "Scania", "MAN", "Mercedes-Benz", "Mercedes", "Benz", "DAF", "Iveco", "Renault"]

# English part vocabulary used to recognise description-only inquiry lines.
PART_TERMS = [
    "brake pad", "brake disc", "brake drum", "brake shoe", "brake chamber", "brake caliper", "oil filter", "air filter",
    "fuel filter", "filter", "air spring", "air bag", "shock absorber", "clutch kit", "clutch disc", "clutch cover",
    "release bearing", "water pump", "radiator", "thermostat", "fan clutch", "sensor", "head lamp", "headlamp",
    "tail lamp", "lamp", "light", "valve", "bearing", "pump", "spring", "absorber", "pad", "disc", "drum", "mirror",
]

QTY_PATTERNS = [
    re.compile(r"\b(?:qty|quantity|q'ty)\s*[:=]?\s*(\d+)", re.I),
    re.compile(r"\b(\d+)\s*(?:pcs|pc|pieces|units|sets|set|nos)\b", re.I),
    re.compile(r"(?:^|\s)[x×\*]\s*(\d+)\b", re.I),
    re.compile(r"(\d+)\s*个|(\d+)\s*件|(\d+)\s*套"),
]
PART_NO_PATTERN = re.compile(
    r"(?<![\w])(?:[A-Z]{1,3}[\s.\-]?)?\d[\d\s.\-/]{2,}\d(?:[\s.\-]?[A-Z]{1,2}\b)?|(?<![\w])[A-Z]{1,3}\s?\d{3,}[A-Z0-9\-]*",
    re.I,
)
FILLER = re.compile(r"\b(hello|hi|dear|also|please|quote|price for|need|we are|we're|looking for|send|catalog|and)\b[,.!]?", re.I)
COMPANY_SUFFIX = re.compile(r"\b(AB|Ltd|Limited|GmbH|Inc|LLC|S\.?A\.?|Co\.?|Company|Corp|B\.?V\.?|S\.?r\.?l\.?|Trading|Parts|Service)\b\.?$", re.I)
SKIP_LINE = re.compile(r"^\s*(hi|hello|dear|thanks|thank you|best|regards|kind regards|br|sincerely|please|we need|looking forward)\b", re.I)

# Column header synonyms for supplier price lists (Chinese and English).
COLUMN_SYNONYMS = {
    "supplier_part_no": ["货号", "型号", "编号", "产品编号", "item no", "item", "model", "model no", "code", "our ref"],
    "name": ["品名", "名称", "产品名称", "description", "product name", "product", "name", "part name"],
    "category": ["类别", "分类", "category", "type"],
    "oe_numbers": ["oe号", "oe", "原厂号", "oem no", "oe no", "oe number", "oem", "原厂编号", "oe编号"],
    "cross_numbers": ["参考号", "对照号", "互换号", "cross ref", "cross reference", "reference", "ref no", "cross"],
    "brand": ["适用品牌", "品牌", "车型品牌", "make", "brand", "truck brand"],
    "vehicle": ["适用车型", "车型", "application", "vehicle", "fits"],
    "specs": ["规格", "尺寸", "size", "dimension", "specification", "spec"],
    "cost_price": ["单价", "价格", "含税价", "出厂价", "price", "unit price", "fob price", "cost"],
    "currency": ["币种", "currency"],
    "moq": ["起订量", "最小起订量", "moq", "min order"],
    "lead_time_days": ["交期", "货期", "交货期", "lead time", "delivery", "delivery time"],
    "packaging": ["包装", "包装方式", "packing", "packaging", "package"],
    "weight_kg": ["重量", "净重", "weight", "n.w.", "nw", "net weight"],
}


def chat_json(prompt_code: str, variables: dict) -> dict:
    handler = {
        "parse_inquiry": parse_inquiry,
        "map_columns": map_columns,
        "extract_pdf_rows": lambda v: {"rows": []},
        "listing_alibaba": lambda v: listing(v, "alibaba"),
        "listing_shopify": lambda v: listing(v, "shopify"),
        "fill_missing": fill_missing,
    }[prompt_code]
    return handler(variables)


def chat_text(prompt_code: str, variables: dict) -> str:
    if prompt_code == "quote_email":
        return quote_email(variables)
    raise KeyError(prompt_code)


def vision_json(prompt_code: str, image_path: str) -> dict:
    """Demo images carry their ground truth in a PNG text chunk written by seed_demo."""
    from PIL import Image

    try:
        with Image.open(image_path) as img:
            label = img.info.get("demo_label")
        if label:
            return json.loads(label)
    except Exception:
        pass
    return {
        "part_type": "brake pad set",
        "part_type_cn": "刹车片",
        "visible_numbers": [],
        "brand": None,
        "features": ["with wear indicator"],
        "description": "heavy duty truck disc brake pad set (mock result: configure VISION_MODEL for real recognition)",
    }


# ---------------------------------------------------------------- inquiry

def _extract_qty(line: str) -> tuple[int, str]:
    for pattern in QTY_PATTERNS:
        m = pattern.search(line)
        if m:
            qty = int(next(g for g in m.groups() if g))
            return qty, line[: m.start()] + " " + line[m.end():]
    return 1, line


def parse_inquiry(variables: dict) -> dict:
    lines = []
    customer = None
    for raw in variables.get("text", "").splitlines():
        line = re.sub(r"^\s*(?:\d{1,2}[.)、]|[-•*])\s+", "", raw).strip()
        if not line:
            continue
        if re.match(r"^(from|company)\s*:", line, re.I):
            customer = line.split(":", 1)[1].strip()
            continue
        if SKIP_LINE.match(line) and not PART_NO_PATTERN.search(line) and not any(t in line.lower() for t in PART_TERMS):
            continue
        qty, rest = _extract_qty(line)
        vehicle = next((m for m in TRUCK_MAKES if re.search(rf"\b{re.escape(m)}\b", rest, re.I)), None)
        numbers = [re.sub(r"^(?:OEM?|REF|NO)\b[\s.:#]*", "", n.strip(" .-"), flags=re.I) for n in PART_NO_PATTERN.findall(rest)]
        numbers = [n for n in numbers if sum(c.isdigit() for c in n) >= 4]
        lowered = rest.lower()
        term = next((t for t in PART_TERMS if t in lowered), None)
        if not numbers and not term:
            continue
        description = rest
        for n in numbers:
            description = description.replace(n, " ")
        description = re.sub(r"\b(oe|oem|no|ref|part|number|p/n)\b[.:#]*", " ", description, flags=re.I)
        description = FILLER.sub(" ", description)
        description = re.sub(r"\s+", " ", description).strip(" ,.:;-")
        if numbers:
            for n in numbers:
                lines.append({"part_no": n, "description": description or (term or ""), "qty": qty, "vehicle": vehicle})
        else:
            lines.append({"part_no": None, "description": description, "qty": qty, "vehicle": vehicle})
    if not customer:
        tail = [l.strip() for l in variables.get("text", "").splitlines() if l.strip()][-3:]
        customer = next((l for l in reversed(tail) if COMPANY_SUFFIX.search(l)), None)
    return {"customer": customer, "lines": lines}


# ---------------------------------------------------------------- ingest

def _clean_header(h: str) -> str:
    return re.sub(r"[\s_()（）/:：.]+", " ", str(h)).strip().lower()


def map_columns(variables: dict) -> dict:
    headers = variables.get("headers", [])
    choices = {syn: field for field, syns in COLUMN_SYNONYMS.items() for syn in syns}
    mapping, used = {}, set()
    for header in headers:
        cleaned = _clean_header(header)
        field = choices.get(cleaned)
        if not field:
            match = process.extractOne(cleaned, list(choices), scorer=fuzz.WRatio, score_cutoff=86)
            field = choices[match[0]] if match else None
        if field in used and field not in ("specs",):
            field = None
        if field:
            used.add(field)
        mapping[str(header)] = field
    return {"mapping": mapping}


# ---------------------------------------------------------------- content

def _makes(product: dict) -> list[str]:
    seen = []
    for f in product.get("fitment", []):
        make = f.split(" ")[0]
        if make not in seen:
            seen.append(make)
    return seen


def listing(variables: dict, platform: str) -> dict:
    p = variables["product"]
    if isinstance(p, str):
        p = json.loads(p)
    oes = [n["number"] for n in p.get("oe_numbers", [])]
    crosses = [f'{n["brand"]} {n["number"]}' for n in p.get("cross_numbers", [])]
    makes = _makes(p) or [n["brand"] for n in p.get("oe_numbers", [])][:1]
    make_text = "/".join(makes[:3])
    spec_text = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in list(p.get("specs", {}).items())[:3])
    name = p.get("name_en") or p.get("category_en", "Truck Part")
    if platform == "alibaba":
        title = f"{name} for {make_text} Truck OE {' '.join(oes[:2])}".strip()
        if len(title) < 110 and spec_text:
            title = f"{title} {spec_text.split(',')[0]}"
        keywords = [f"{make_text} {p.get('category_en', '')}".strip(), f"{oes[0]} {name}" if oes else name, f"truck {p.get('category_en', '').lower()}"]
    else:
        title = f"{name} | {make_text} | OE {oes[0]}" if oes else f"{name} | {make_text}"
        keywords = [p.get("category_en", ""), *makes[:3], "heavy duty truck", "OE replacement"]
    bullets = [
        f"Direct fit for {', '.join(p.get('fitment', [])[:3]) or make_text + ' trucks'}.",
        f"OE-equivalent replacement for {', '.join(oes[:3]) or 'original part'}; cross reference {', '.join(crosses[:2]) or 'available on request'}.",
        f"Key specifications: {spec_text or 'see description'}.",
        f"Packed {p.get('qty_per_package') or 1} pc per box, weight {p.get('weight_kg') or '-'} kg, export carton for safe shipping.",
        "Stable supply from audited factories, 12-month warranty, samples available.",
    ]
    description = (
        f"{name} designed for {make_text} heavy-duty trucks. "
        f"OE numbers: {', '.join(oes) or '-'}. Cross reference: {', '.join(crosses) or '-'}. "
        f"Specifications: {spec_text or '-'}. "
        f"Fits: {'; '.join(p.get('fitment', [])) or '-'}. "
        "Please confirm the OE number on your old part before ordering; our team checks fitment for every order."
    )
    faq = [
        {"q": "How can I confirm this part fits my truck?", "a": "Send us the OE number printed on your original part or your VIN; we cross-check fitment before shipping."},
        {"q": "What is the MOQ?", "a": "Samples are available; wholesale orders usually start from 10 pcs per item."},
        {"q": "What is the warranty?", "a": "12 months from delivery against manufacturing defects."},
    ]
    if platform == "alibaba":
        faq.append({"q": "Can you pack with our brand?", "a": "Yes, OEM packaging is available for bulk orders."})
    return {"title": title[:128 if platform == "alibaba" else 70], "keywords": keywords, "bullets": bullets, "description": description, "faq": faq}


def quote_email(variables: dict) -> str:
    items = variables["items"]
    if isinstance(items, str):
        items = json.loads(items)
    rows = "\n".join(
        f"  {i + 1}. {it['sku']} (your ref. {it['requested'] or '-'}) {it['name']} — {it['qty']} pcs x USD {it['unit_price']} = USD {it['subtotal']}"
        + {"exact": "", "fuzzy": "  [closest match to your ref., please confirm the number]"}.get(it.get("method"), "  [suggested by description, please confirm fitment]")
        for i, it in enumerate(items)
    )
    lead = max((it.get("lead_time_days") or 0 for it in items), default=0)
    return (
        f"Dear {variables.get('customer') or 'Customer'},\n\n"
        "Thank you for your inquiry. Please find our best offer below:\n\n"
        f"{rows}\n\n"
        f"Total: USD {variables['total']} (FOB China)\n"
        f"Estimated lead time: {lead or 'to be confirmed'} days\n"
        "Price validity: 15 days. MOQ may apply per item.\n\n"
        "All alternative parts are cross-referenced by OE number and equivalent in fitment.\n"
        "Please let us know if you need photos or samples.\n\n"
        "Best regards,\nSales Team"
    )


def fill_missing(variables: dict) -> dict:
    product = variables["product"]
    if isinstance(product, str):
        product = json.loads(product)
    missing = variables.get("missing", [])
    suggestions = {}
    category_en = product.get("category_en", "truck part")
    if "name_en" in missing:
        makes = _makes(product)
        suggestions["name_en"] = {
            "value": f"{category_en} for {'/'.join(makes) or 'Heavy Duty Truck'}",
            "reason": f"根据品类「{product.get('category')}」和适配车型推断",
        }
    if "description_en" in missing:
        oes = ", ".join(n["number"] for n in product.get("oe_numbers", [])) or "-"
        suggestions["description_en"] = {
            "value": f"{product.get('name_en') or category_en} for heavy-duty trucks. OE numbers: {oes}. "
                     f"Fits: {'; '.join(product.get('fitment', [])) or 'please confirm by OE number'}. "
                     "OE-equivalent quality, tested for durability, 12-month warranty.",
            "reason": "根据产品名称、OE 号和适配车型生成，需人工确认措辞",
        }
    return {"suggestions": suggestions}


# ---------------------------------------------------------------- embedding

_TOKEN = re.compile(r"[a-z]+|\d+|[一-鿿]")
_STOP = {"for", "the", "and", "with", "of", "a", "an", "to", "in", "truck", "trucks", "heavy", "duty", "set", "kit", "mm"}


def _tokens(text: str) -> list[str]:
    text = text.lower()
    raw = _TOKEN.findall(text)
    tokens = []
    for t in raw:
        if t in _STOP:
            continue
        if len(t) > 3 and t.endswith("s") and t.isalpha():
            t = t[:-1]
        tokens.append(t)
    # CJK bigrams and word bigrams carry most of the meaning in short part names.
    tokens += [a + b for a, b in zip(raw, raw[1:]) if a not in _STOP and b not in _STOP]
    tokens += [normalize_part_no(w) for w in re.findall(r"[\w.\-]*\d[\w.\-]*", text) if len(w) >= 5]
    return tokens


def embed(text: str, dim: int) -> list[float]:
    """Feature hashing: no semantics, but overlapping words give high cosine similarity."""
    vec = [0.0] * dim
    for token in _tokens(text):
        h = int.from_bytes(hashlib.md5(token.encode()).digest()[:8], "little")
        vec[h % dim] += 1.0 if (h >> 32) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

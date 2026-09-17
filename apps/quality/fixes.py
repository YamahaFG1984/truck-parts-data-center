"""Fix actions for quality issues (DESIGN.md §7.3)."""

import re

from django.db import transaction
from django.db.models import Q

from apps.ai import client as ai
from apps.ai.schemas import FillMissing
from apps.catalog.models import Fitment, PartNumber, Product, ProductImage
from apps.catalog.services import product_detail_queryset, product_payload
from apps.suppliers.models import SupplierOffer

from .rules import SPEC_KEY, UNIT_TEXT

KEY_TRANSLATIONS = {"直径": "diameter", "厚度": "thickness", "高度": "height", "长度": "length", "宽度": "width", "外径": "outer_diameter", "内径": "inner_diameter"}
UNIT_IN_KEY = re.compile(r"\s*[\(（]?\s*(mm|毫米)\s*[\)）]?\s*$", re.I)
FILLABLE = ("name_en", "description_en")


def _normalize_spec(key: str, value):
    has_mm = bool(UNIT_IN_KEY.search(key)) or (isinstance(value, str) and bool(UNIT_TEXT.search(value)))
    base = UNIT_IN_KEY.sub("", key).strip()
    for cn, en in KEY_TRANSLATIONS.items():
        base = base.replace(cn, en)
    base = re.sub(r"[^0-9a-zA-Z]+", "_", base).strip("_").lower()
    if isinstance(value, str) and has_mm:
        number = re.search(r"\d+(?:\.\d+)?", value)
        if number:
            value = float(number.group())
            value = int(value) if value.is_integer() else value
    if has_mm and not base.endswith("_mm"):
        base = f"{base}_mm"
    return base, value


def fix_units(products=None) -> int:
    """Rewrite spec keys to snake_case_unit and strip unit text from values. Deterministic, no AI."""
    fixed = 0
    qs = products if products is not None else Product.objects.exclude(status=Product.ARCHIVED)
    for product in qs:
        specs = product.specs or {}
        if all(SPEC_KEY.match(k) and not (isinstance(v, str) and UNIT_TEXT.search(v)) for k, v in specs.items()):
            continue
        product.specs = dict(_normalize_spec(k, v) for k, v in specs.items())
        product.save(update_fields=["specs", "updated_at"])
        fixed += 1
    return fixed


def fix_number_format() -> int:
    fixed = 0
    for pn in PartNumber.objects.filter(Q(number__startswith=" ") | Q(number__endswith=" ") | Q(number__contains="  ")):
        pn.number = " ".join(pn.number.split())
        pn.save()
        fixed += 1
    return fixed


@transaction.atomic
def merge_products(keep: Product, remove: Product) -> dict:
    """Move numbers, fitments, offers and images to `keep`, archive `remove`."""
    moved = {"numbers": 0, "fitments": 0, "offers": 0, "images": 0}
    existing = {pn.normalized: pn for pn in keep.part_numbers.all()}
    for pn in remove.part_numbers.all():
        kept = existing.get(pn.normalized)
        if kept:
            if kept.brand_id is None and pn.brand_id:
                kept.brand_id = pn.brand_id
                kept.save()
            pn.delete()
        else:
            pn.product = keep
            pn.save()
            moved["numbers"] += 1
    fitted = set(keep.fitments.values_list("vehicle_model_id", flat=True))
    for f in remove.fitments.all():
        if f.vehicle_model_id in fitted:
            f.delete()
        else:
            Fitment.objects.filter(pk=f.pk).update(product=keep)
            moved["fitments"] += 1
    moved["offers"] = SupplierOffer.objects.filter(product=remove).update(product=keep)
    if not keep.images.exists():
        moved["images"] = ProductImage.objects.filter(product=remove).update(product=keep)
    for field in ("name_en", "name_cn", "description_en", "weight_kg", "package_l_cm", "package_w_cm", "package_h_cm", "qty_per_package"):
        if not getattr(keep, field) and getattr(remove, field):
            setattr(keep, field, getattr(remove, field))
    if not keep.specs and remove.specs:
        keep.specs = remove.specs
    keep.save()
    remove.status = Product.ARCHIVED
    remove.merged_into = keep
    remove.save(update_fields=["status", "merged_into", "updated_at"])
    return moved


def missing_fields(product: Product) -> list[str]:
    missing = []
    if not product.name_en:
        missing.append("name_en")
    if len(product.description_en or "") < 50:
        missing.append("description_en")
    return missing


def suggest_missing(product: Product) -> dict:
    missing = missing_fields(product)
    if not missing:
        return {}
    references = list(
        product_detail_queryset().filter(category=product.category, status=Product.ACTIVE)
        .exclude(pk=product.pk).order_by("-completeness_score")[:3]
    )
    result = ai.chat_json("quality_fill_missing", "fill_missing", {
        "product": product_payload(product),
        "missing": missing,
        "references": [product_payload(p) for p in references],
    }, FillMissing)
    # Only whitelisted text fields may be written; numbers, prices and fitment never come from AI.
    return {k: v.model_dump() for k, v in result.suggestions.items() if k in FILLABLE and k in missing and isinstance(v.value, str)}


def accept_suggestions(product: Product, values: dict[str, str]) -> list[str]:
    changed = []
    for field, value in values.items():
        if field in FILLABLE and value.strip():
            setattr(product, field, value.strip())
            changed.append(field)
    if changed:
        product.save(update_fields=[*changed, "updated_at"])
    return changed

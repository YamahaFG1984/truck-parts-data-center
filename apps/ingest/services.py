"""Write reviewed import rows into master data (DESIGN.md §9 step 5, ADR-08)."""

import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from rapidfuzz import fuzz, process

from apps.ai.embeddings import refresh_product_embeddings
from apps.catalog.models import Brand, Category, PartNumber, Product
from apps.core.utils import normalize_part_no
from apps.quality.scan import run_scan
from apps.suppliers.models import SupplierOffer

from .extract import split_brand
from .models import ImportBatch, ImportRow

CJK = re.compile(r"[一-鿿]")


def _oe_brand(row: dict, product: Product | None) -> Brand | None:
    text = " ".join(filter(None, [row.get("brand"), row.get("vehicle"), row.get("name")])).lower()
    for brand in Brand.objects.filter(type=Brand.OEM):
        if brand.name.lower().split("-")[0] in text:
            return brand
    if product:
        brands = {pn.brand for pn in product.part_numbers.filter(type=PartNumber.OE)}
        if len(brands) == 1:
            return brands.pop()
    return None


def _add_number(product: Product, number: str, type_: str, brand: Brand | None) -> bool:
    normalized = normalize_part_no(number)
    if not normalized or product.part_numbers.filter(normalized=normalized).exists():
        return False
    PartNumber.objects.create(product=product, number=number.strip(), type=type_, brand=brand)
    return True


def _apply(row: ImportRow, product: Product) -> None:
    data = row.extracted
    batch = row.batch
    oe_brand = _oe_brand(data, product)
    for number in data.get("oe_numbers", []):
        _add_number(product, number, PartNumber.OE, oe_brand)
    for raw in data.get("cross_numbers", []):
        brand, number = split_brand(raw)
        _add_number(product, number, PartNumber.CROSS, brand)
    if data.get("supplier_part_no"):
        _add_number(product, data["supplier_part_no"], PartNumber.SUPPLIER, None)
    if data.get("cost_price"):
        SupplierOffer.objects.create(
            supplier=batch.supplier, product=product, supplier_part_no=data.get("supplier_part_no") or "",
            cost_price=Decimal(str(data["cost_price"])), currency=data.get("currency") or "CNY",
            moq=data.get("moq"), lead_time_days=data.get("lead_time_days"), packaging=data.get("packaging") or "",
            quoted_at=batch.created_at.date(), source_import_row=row,
        )
    if data.get("weight_kg") and not product.weight_kg:
        product.weight_kg = Decimal(str(data["weight_kg"]))
        product.save(update_fields=["weight_kg", "updated_at"])


def _guess_category(row: dict) -> Category:
    text = " ".join(filter(None, [row.get("category"), row.get("name")]))
    leaves = list(Category.objects.filter(children__isnull=True))
    choices = {c.id: f"{c.name} {c.name_en}" for c in leaves}
    match = process.extractOne(text, choices, scorer=fuzz.partial_ratio, score_cutoff=70) if text else None
    if match:
        return next(c for c in leaves if c.id == match[2])
    return Category.objects.get_or_create(name="待分类", defaults={"name_en": "Unclassified"})[0]


def _next_sku() -> str:
    last = Product.objects.filter(sku__startswith="FIT-").aggregate(m=Max("sku"))["m"] or "FIT-00000"
    return f"FIT-{int(last.split('-')[1]) + 1:05d}"


@transaction.atomic
def approve(row: ImportRow, product: Product | None = None) -> Product:
    product = product or row.matched_product
    if product is None:
        raise ValueError("该行没有匹配产品，请选择产品或新建 SKU")
    _apply(row, product)
    row.matched_product = product
    row.status = ImportRow.APPROVED
    row.save()
    return product


@transaction.atomic
def create_product(row: ImportRow) -> Product:
    data = row.extracted
    name = data.get("name") or ""
    product = Product.objects.create(
        sku=_next_sku(),
        name_en="" if CJK.search(name) else name,
        name_cn=name if CJK.search(name) else "",
        category=_guess_category(data),
        specs={},
        status=Product.DRAFT,
    )
    _apply(row, product)
    row.matched_product = product
    row.match_method = "new"
    row.status = ImportRow.NEW_PRODUCT
    row.save()
    return product


def reject(row: ImportRow) -> None:
    row.status = ImportRow.REJECTED
    row.save(update_fields=["status"])


def refresh_batch(batch: ImportBatch, product_ids: set[int]) -> None:
    """Keep stats, search vectors and quality scores in sync after review actions."""
    if product_ids:
        refresh_product_embeddings(Product.objects.filter(id__in=product_ids))
        run_scan(product_ids)
    rows = batch.rows.all()
    batch.stats = {
        **batch.stats,
        "approved": rows.filter(status=ImportRow.APPROVED).count(),
        "new_product": rows.filter(status=ImportRow.NEW_PRODUCT).count(),
        "rejected": rows.filter(status=ImportRow.REJECTED).count(),
        "pending": rows.filter(status=ImportRow.PENDING).count(),
    }
    if batch.stats["pending"] == 0 and batch.status == ImportBatch.REVIEWING:
        batch.status = ImportBatch.DONE
    batch.save()

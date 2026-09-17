from django.db.models import Prefetch, Q

from apps.core.utils import normalize_part_no

from .models import PartNumber, Product


def product_detail_queryset():
    return Product.objects.select_related("category", "merged_into").prefetch_related(
        "images", Prefetch("part_numbers", queryset=PartNumber.objects.select_related("brand")),
        "fitments__vehicle_model", "offers__supplier",
    )


def search_products(q: str):
    qs = Product.objects.all()
    if q:
        n = normalize_part_no(q)
        qs = qs.filter(
            Q(sku__icontains=q) | Q(name_en__icontains=q) | Q(name_cn__icontains=q)
            | Q(part_numbers__normalized__icontains=n)
        ).distinct()
    return qs


def product_payload(product: Product) -> dict:
    """Product facts sent to the LLM. Deliberately excludes cost prices and suppliers (DESIGN.md §8.4)."""
    return {
        "sku": product.sku,
        "name_en": product.name_en,
        "name_cn": product.name_cn,
        "category": product.category.name,
        "category_en": product.category.name_en,
        "specs": product.specs,
        "oe_numbers": [{"brand": pn.brand.name if pn.brand else "", "number": pn.number} for pn in product.oe_numbers],
        "cross_numbers": [{"brand": pn.brand.name if pn.brand else "", "number": pn.number} for pn in product.cross_numbers],
        "fitment": [str(f.vehicle_model) for f in product.fitments.all()],
        "weight_kg": float(product.weight_kg) if product.weight_kg else None,
        "qty_per_package": product.qty_per_package,
        "description_en": product.description_en,
    }

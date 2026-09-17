from django.db import transaction

from apps.catalog.models import Product

from .models import DataIssue
from .rules import RULES
from .scoring import completeness


def product_queryset():
    return Product.objects.exclude(status=Product.ARCHIVED).select_related("category").prefetch_related(
        "images", "part_numbers__brand", "fitments", "offers"
    )


@transaction.atomic
def run_scan(product_ids=None) -> dict:
    qs = product_queryset()
    if product_ids is not None:
        qs = qs.filter(id__in=product_ids)
    products = list(qs)
    ids = [p.id for p in products]

    DataIssue.objects.filter(product_id__in=ids, resolved=False).delete()
    # Archived (merged) products should not keep open issues.
    DataIssue.objects.filter(product__status=Product.ARCHIVED, resolved=False).delete()

    issues = []
    for r in RULES:
        for issue in r.fn(products):
            issues.append(DataIssue(
                product_id=issue.product_id, rule_code=r.code, category=r.category, severity=r.severity,
                field=issue.field, message=issue.message[:300], related_product_id=issue.related_product_id,
            ))
    DataIssue.objects.bulk_create(issues)

    for p in products:
        p.completeness_score = completeness(p)[0]
    Product.objects.bulk_update(products, ["completeness_score"])
    return {"products": len(products), "issues": len(issues)}

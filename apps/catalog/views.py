from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.quality.scoring import WEIGHTS, completeness
from apps.suppliers.pricing import price_product

from .models import Category, Product
from .services import product_detail_queryset, search_products

SORTS = {"score": "completeness_score", "-score": "-completeness_score", "sku": "sku", "-updated": "-updated_at"}


def product_list(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    status = request.GET.get("status", "")
    sort = request.GET.get("sort", "sku")
    qs = search_products(q).select_related("category").prefetch_related("images", "part_numbers__brand", "issues")
    if category:
        qs = qs.filter(category_id=category)
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.exclude(status=Product.ARCHIVED)
    qs = qs.order_by(SORTS.get(sort, "sku"))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "catalog/product_list.html", {
        "page": page, "q": q, "category": category, "status": status, "sort": sort,
        "categories": Category.objects.filter(children__isnull=True).order_by("name"),
        "statuses": Product.STATUS_CHOICES,
    })


def product_detail(request, pk):
    product = get_object_or_404(product_detail_queryset(), pk=pk)
    score, parts = completeness(product)
    return render(request, "catalog/product_detail.html", {
        "product": product,
        "score": score,
        "score_parts": [(k, parts[k], WEIGHTS[k]) for k in WEIGHTS],
        "pricing": price_product(product),
        "issues": product.issues.filter(resolved=False),
        "listings": product.listings.all(),
        "merged_from": product.merged_from.all(),
    })

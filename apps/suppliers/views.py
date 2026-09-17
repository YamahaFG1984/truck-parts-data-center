from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, render

from .models import Supplier


def supplier_list(request):
    suppliers = Supplier.objects.annotate(offer_count=Count("offers"), product_count=Count("offers__product", distinct=True), last_quote=Max("offers__quoted_at"))
    return render(request, "suppliers/list.html", {"suppliers": suppliers})


def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    offers = supplier.offers.select_related("product__category").order_by("-quoted_at")[:200]
    return render(request, "suppliers/detail.html", {"supplier": supplier, "offers": offers, "batches": supplier.import_batches.all()[:10]})

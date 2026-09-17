from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.ai.client import AIError
from apps.catalog.models import Product
from apps.catalog.services import product_detail_queryset

from .generate import generate, shopify_csv, validate
from .models import ListingContent


def listing_list(request):
    platform = request.GET.get("platform", "")
    listings = ListingContent.objects.select_related("product__category").prefetch_related("product__images")
    if platform:
        listings = listings.filter(platform=platform)
    ready = (Product.objects.filter(status=Product.ACTIVE, completeness_score__gte=85, listings__isnull=True)
             .select_related("category").order_by("-completeness_score")[:12])
    return render(request, "listing/list.html", {"listings": listings[:100], "ready": ready, "platform": platform})


@require_POST
def generate_view(request, product_pk, platform):
    if platform not in ("alibaba", "shopify"):
        return redirect("listing:list")
    product = get_object_or_404(product_detail_queryset(), pk=product_pk)
    try:
        listing = generate(product, platform)
    except AIError as exc:
        messages.error(request, f"AI 生成失败：{exc}")
        return redirect("catalog:detail", pk=product_pk)
    return redirect("listing:edit", pk=listing.pk)


def edit(request, pk):
    listing = get_object_or_404(ListingContent.objects.select_related("product__category"), pk=pk)
    if request.method == "POST":
        listing.title = request.POST.get("title", "").strip()
        listing.keywords = [k.strip() for k in request.POST.get("keywords", "").split(",") if k.strip()]
        listing.bullets = [b.strip() for b in request.POST.get("bullets", "").splitlines() if b.strip()]
        listing.description = request.POST.get("description", "").strip()
        faq = []
        for block in request.POST.get("faq", "").split("\n\n"):
            lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
            if len(lines) >= 2:
                faq.append({"q": lines[0].removeprefix("Q:").strip(), "a": " ".join(lines[1:]).removeprefix("A:").strip()})
        listing.faq = faq
        listing.warnings = validate(listing)
        listing.status = "confirmed" if request.POST.get("confirm") else "draft"
        listing.save()
        messages.success(request, "已保存" + ("并确认" if listing.status == "confirmed" else "为草稿"))
        return redirect("listing:edit", pk=pk)
    faq_text = "\n\n".join(f"Q: {f['q']}\nA: {f['a']}" for f in listing.faq)
    return render(request, "listing/edit.html", {"listing": listing, "product": listing.product, "faq_text": faq_text,
                                                 "title_limit": 128 if listing.platform == "alibaba" else 70})


def export_shopify(request):
    listings = ListingContent.objects.filter(platform="shopify", status="confirmed").select_related("product__category").prefetch_related("product__images")
    response = HttpResponse("﻿" + shopify_csv(listings), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="shopify_products.csv"'
    return response

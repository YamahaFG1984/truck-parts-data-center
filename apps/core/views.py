from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.ai.models import AICallLog
from apps.catalog.models import PartNumber, Product
from apps.ingest.models import ImportBatch, ImportRow
from apps.inquiry.models import Inquiry, InquiryLine
from apps.listing.models import ListingContent
from apps.quality.models import DataIssue
from apps.suppliers.models import Supplier, SupplierOffer


def dashboard(request):
    since = timezone.now() - timedelta(days=7)
    active = Product.objects.exclude(status=Product.ARCHIVED)
    feedback = InquiryLine.objects.exclude(feedback="").aggregate(
        correct=Count("id", filter=Q(feedback="correct")), total=Count("id"))
    lines = InquiryLine.objects.filter(inquiry__created_at__gte=since)
    line_stats = lines.aggregate(total=Count("id"), matched=Count("id", filter=Q(selected_product__isnull=False)))
    ai_stats = AICallLog.objects.filter(created_at__gte=since).aggregate(n=Count("id"), avg=Avg("latency_ms"), failed=Count("id", filter=Q(success=False)))
    context = {
        "kpi": {
            "products": active.count(),
            "numbers": PartNumber.objects.exclude(product__status=Product.ARCHIVED).count(),
            "avg_score": round(active.aggregate(a=Avg("completeness_score"))["a"] or 0, 1),
            "issues": DataIssue.objects.filter(resolved=False).count(),
            "suppliers": Supplier.objects.count(),
            "offers": SupplierOffer.objects.count(),
            "inquiries_7d": Inquiry.objects.filter(created_at__gte=since).count(),
            "avg_inquiry_ms": round(Inquiry.objects.filter(created_at__gte=since).aggregate(a=Avg("elapsed_ms"))["a"] or 0),
            "match_rate": round(100 * line_stats["matched"] / line_stats["total"]) if line_stats["total"] else None,
            "feedback_accuracy": round(100 * feedback["correct"] / feedback["total"]) if feedback["total"] else None,
            "feedback_total": feedback["total"],
            "pending_rows": ImportRow.objects.filter(status=ImportRow.PENDING, batch__status=ImportBatch.REVIEWING).count(),
            "listings": ListingContent.objects.count(),
            "ai_calls": ai_stats["n"],
            "ai_avg_ms": round(ai_stats["avg"] or 0),
            "ai_failed": ai_stats["failed"],
        },
        "no_image": active.filter(images__isnull=True).count(),
        "no_oe": active.exclude(part_numbers__type=PartNumber.OE).count(),
        "no_offer": active.filter(offers__isnull=True).count(),
        "recent_inquiries": Inquiry.objects.prefetch_related("lines")[:5],
        "recent_batches": ImportBatch.objects.select_related("supplier")[:5],
        "top_issues": DataIssue.objects.filter(resolved=False).values("rule_code").annotate(n=Count("id")).order_by("-n")[:5],
    }
    return render(request, "core/dashboard.html", context)

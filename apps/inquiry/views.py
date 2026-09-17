import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.files import File
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.ai.client import AIError

from . import services
from .models import Inquiry, InquiryLine
from .pdf import quotation_pdf

DEMO_DIR = Path(settings.BASE_DIR) / "demo_data"


def _samples():
    try:
        return json.loads((DEMO_DIR / "sample_inquiries.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def _demo_photos():
    return sorted(p.name for p in (DEMO_DIR / "inquiry_photos").glob("*.png"))


def workbench(request):
    if request.method == "POST":
        text = request.POST.get("raw_text", "")
        image = request.FILES.get("image")
        demo_photo = request.POST.get("demo_photo")
        if not text.strip() and not image and not demo_photo:
            messages.error(request, "请输入询价内容或上传图片")
            return redirect("inquiry:workbench")
        inquiry = Inquiry(customer=request.POST.get("customer", "")[:100], channel=request.POST.get("channel", "email"), raw_text=text)
        if image:
            inquiry.image = image
        elif demo_photo in _demo_photos():
            with open(DEMO_DIR / "inquiry_photos" / demo_photo, "rb") as fh:
                inquiry.image.save(demo_photo, File(fh), save=False)
        try:
            services.run_inquiry(inquiry)
        except AIError as exc:
            messages.error(request, f"AI 调用失败：{exc}")
            return redirect("inquiry:workbench")
        return redirect("inquiry:detail", pk=inquiry.pk)
    return render(request, "inquiry/workbench.html", {
        "samples": _samples(), "demo_photos": _demo_photos(),
        "recent": Inquiry.objects.prefetch_related("lines")[:8], "channels": Inquiry.CHANNEL_CHOICES,
    })


def detail(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    return render(request, "inquiry/detail.html", {"inquiry": inquiry, "rows": services.hydrate_lines(inquiry), "items": services.quote_items(inquiry)})


@require_POST
def select(request, pk, line_id):
    line = get_object_or_404(InquiryLine, pk=line_id, inquiry_id=pk)
    product_id = request.POST.get("product_id")
    if product_id is not None:
        line.selected_product_id = int(product_id) if product_id and int(product_id) in {c["product_id"] for c in line.candidates} else None
    try:
        line.qty = max(1, int(request.POST.get("qty", line.qty)))
    except ValueError:
        pass
    services.update_line_price(line)
    row = next(r for r in services.hydrate_lines(line.inquiry) if r["line"].pk == line.pk)
    response = render(request, "inquiry/_line.html", {"inquiry": line.inquiry, "row": row})
    response["HX-Trigger"] = "quoteChanged"
    return response


@require_POST
def feedback(request, pk, line_id):
    line = get_object_or_404(InquiryLine, pk=line_id, inquiry_id=pk)
    value = request.POST.get("feedback", "")
    line.feedback = value if value in dict(InquiryLine.FEEDBACK_CHOICES) else ""
    line.feedback_note = request.POST.get("note", "")[:300]
    line.save(update_fields=["feedback", "feedback_note"])
    return render(request, "inquiry/_feedback.html", {"inquiry": line.inquiry, "line": line})


def quote_summary(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    return render(request, "inquiry/_quote_summary.html", {"inquiry": inquiry, "items": services.quote_items(inquiry)})


@require_POST
def quote_email(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    text, warnings = services.generate_quote_email(inquiry)
    return render(request, "inquiry/_quote_email.html", {"inquiry": inquiry, "text": text, "warnings": warnings})


def quote_pdf(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    response = HttpResponse(quotation_pdf(inquiry, services.quote_items(inquiry)), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Quotation-Q{inquiry.pk:05d}.pdf"'
    return response


def history(request):
    page = Paginator(Inquiry.objects.prefetch_related("lines"), 20).get_page(request.GET.get("page"))
    return render(request, "inquiry/history.html", {"page": page})

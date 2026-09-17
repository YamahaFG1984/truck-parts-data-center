from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.files import File
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_q.tasks import async_task

from apps.catalog.models import Product
from apps.suppliers.models import Supplier

from . import services
from .models import ImportBatch, ImportRow

ALLOWED = {".xlsx", ".xls", ".xlsm", ".csv", ".pdf"}
DEMO_DIR = Path(settings.BASE_DIR) / "demo_data"


def _demo_files():
    return sorted(p.name for p in DEMO_DIR.glob("*") if p.suffix.lower() in ALLOWED)


def _enqueue(batch):
    if settings.Q_CLUSTER.get("sync"):
        from .tasks import process_batch

        process_batch(batch.pk)
    else:
        async_task("apps.ingest.tasks.process_batch", batch.pk, task_name=f"import-{batch.pk}")


def batch_list(request):
    if request.method == "POST":
        supplier = Supplier.objects.filter(pk=request.POST.get("supplier")).first()
        upload = request.FILES.get("file")
        demo = request.POST.get("demo_file")
        if not supplier or not (upload or demo in _demo_files()):
            messages.error(request, "请选择供应商并上传文件")
            return redirect("ingest:list")
        batch = ImportBatch(supplier=supplier)
        if upload:
            suffix = Path(upload.name).suffix.lower()
            if suffix not in ALLOWED:
                messages.error(request, f"不支持的文件类型 {suffix}")
                return redirect("ingest:list")
            batch.file_type = suffix[1:]
            batch.file = upload
        else:
            batch.file_type = Path(demo).suffix[1:].lower()
            with open(DEMO_DIR / demo, "rb") as fh:
                batch.file.save(demo, File(fh), save=False)
        batch.save()
        _enqueue(batch)
        return redirect("ingest:detail", pk=batch.pk)
    return render(request, "ingest/list.html", {
        "batches": ImportBatch.objects.select_related("supplier")[:30],
        "suppliers": Supplier.objects.all(),
        "demo_files": _demo_files(),
    })


def batch_detail(request, pk):
    batch = get_object_or_404(ImportBatch.objects.select_related("supplier"), pk=pk)
    status_filter = request.GET.get("status", "")
    rows = batch.rows.select_related("matched_product__category").prefetch_related("matched_product__part_numbers__brand", "matched_product__images")
    if status_filter:
        rows = rows.filter(status=status_filter)
    context = {"batch": batch, "rows": rows, "status_filter": status_filter, "row_statuses": ImportRow.STATUS_CHOICES}
    if request.headers.get("HX-Request") and request.GET.get("progress"):
        if batch.status in (ImportBatch.UPLOADED, ImportBatch.PARSING):
            return render(request, "ingest/_progress.html", context)
        response = render(request, "ingest/_progress.html", context)
        response["HX-Refresh"] = "true"
        return response
    return render(request, "ingest/detail.html", context)


@require_POST
def reprocess(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    batch.status = ImportBatch.UPLOADED
    batch.save(update_fields=["status"])
    _enqueue(batch)
    return redirect("ingest:detail", pk=pk)


@require_POST
def row_action(request, pk):
    row = get_object_or_404(ImportRow.objects.select_related("batch__supplier"), pk=pk)
    action = request.POST.get("action")
    touched = set()
    try:
        if action == "approve":
            product = None
            if request.POST.get("product_sku"):
                product = Product.objects.filter(sku__iexact=request.POST["product_sku"].strip()).first()
                if not product:
                    raise ValueError(f"找不到 SKU {request.POST['product_sku']}")
            touched.add(services.approve(row, product).pk)
        elif action == "new":
            touched.add(services.create_product(row).pk)
        elif action == "reject":
            services.reject(row)
        elif action == "reset":
            row.status = ImportRow.PENDING
            row.save(update_fields=["status"])
        error = ""
    except ValueError as exc:
        error = str(exc)
    services.refresh_batch(row.batch, touched)
    row.refresh_from_db()
    response = render(request, "ingest/_row.html", {"row": row, "batch": row.batch, "error": error})
    response["HX-Trigger"] = "batchChanged"
    return response


@require_POST
def bulk_approve(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    touched = set()
    rows = batch.rows.filter(status=ImportRow.PENDING, preselected=True).select_related("batch__supplier", "matched_product")
    for row in rows:
        touched.add(services.approve(row).pk)
    services.refresh_batch(batch, touched)
    messages.success(request, f"已批量通过 {len(touched)} 个高置信度匹配（≥95），新增的报价和 Cross 号已写入产品库")
    return redirect("ingest:detail", pk=pk)


def stats(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    return render(request, "ingest/_stats.html", {"batch": batch})

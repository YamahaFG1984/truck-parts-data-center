import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.ai.client import AIError
from apps.ai.embeddings import refresh_product_embeddings
from apps.catalog.models import Category, Product
from apps.catalog.services import product_detail_queryset

from . import fixes
from .models import DataIssue
from .rules import RULES, SEVERITY_ORDER, rules_by_code
from .scan import run_scan


def dashboard(request):
    active = Product.objects.exclude(status=Product.ARCHIVED)
    open_issues = DataIssue.objects.filter(resolved=False)
    by_rule = dict(open_issues.values_list("rule_code").annotate(n=Count("id")))
    rules = [{"rule": r, "count": by_rule.get(r.code, 0)} for r in RULES]
    by_category = (
        Category.objects.filter(children__isnull=True)
        .annotate(avg=Avg("products__completeness_score", filter=~Q(products__status=Product.ARCHIVED)), n=Count("products", filter=~Q(products__status=Product.ARCHIVED)))
        .filter(n__gt=0).order_by("avg")
    )
    buckets = [
        ("<60", active.filter(completeness_score__lt=60).count()),
        ("60-79", active.filter(completeness_score__gte=60, completeness_score__lt=80).count()),
        ("80-89", active.filter(completeness_score__gte=80, completeness_score__lt=90).count()),
        ("90-100", active.filter(completeness_score__gte=90).count()),
    ]
    rule_filter = request.GET.get("rule", "")
    severity = request.GET.get("severity", "")
    severity_rank = Case(*[When(severity=k, then=Value(v)) for k, v in SEVERITY_ORDER.items()], output_field=IntegerField())
    issues = open_issues.select_related("product", "related_product").order_by(severity_rank, "rule_code", "product__sku")
    if rule_filter:
        issues = issues.filter(rule_code=rule_filter)
    if severity:
        issues = issues.filter(severity=severity)
    page = Paginator(issues, 25).get_page(request.GET.get("page"))
    rule_map = rules_by_code()
    return render(request, "quality/dashboard.html", {
        "total": active.count(),
        "avg_score": round(active.aggregate(a=Avg("completeness_score"))["a"] or 0, 1),
        "issue_count": open_issues.count(),
        "affected": open_issues.values("product").distinct().count(),
        "rules": rules,
        "page": page,
        "rule_filter": rule_filter,
        "severity": severity,
        "rule_titles": {code: r.title for code, r in rule_map.items()},
        "chart_rules": json.dumps({"labels": [x["rule"].title for x in rules if x["count"]], "data": [x["count"] for x in rules if x["count"]]}, ensure_ascii=False),
        "chart_categories": json.dumps({"labels": [c.name for c in by_category], "data": [round(c.avg or 0, 1) for c in by_category]}, ensure_ascii=False),
        "chart_buckets": json.dumps({"labels": [b[0] for b in buckets], "data": [b[1] for b in buckets]}),
        "fixable_units": by_rule.get("FMT_UNIT", 0),
        "fixable_numbers": by_rule.get("FMT_PART_NUMBER", 0),
    })


@require_POST
def scan(request):
    result = run_scan()
    messages.success(request, f"扫描完成：{result['products']} 个 SKU，发现 {result['issues']} 个问题")
    return redirect("quality:dashboard")


@require_POST
def fix_units(request):
    n = fixes.fix_units()
    run_scan()
    messages.success(request, f"已标准化 {n} 个产品的规格键名与单位")
    return redirect("quality:dashboard")


@require_POST
def fix_numbers(request):
    n = fixes.fix_number_format()
    run_scan()
    messages.success(request, f"已清理 {n} 个号码中的多余空格")
    return redirect("quality:dashboard")


def merge(request, pk, other_pk):
    a = get_object_or_404(product_detail_queryset(), pk=pk)
    b = get_object_or_404(product_detail_queryset(), pk=other_pk)
    if request.method == "POST":
        keep, remove = (a, b) if request.POST.get("keep") == str(a.pk) else (b, a)
        if remove.status == Product.ARCHIVED:
            messages.error(request, f"{remove.sku} 已归档")
            return redirect("catalog:detail", pk=keep.pk)
        moved = fixes.merge_products(keep, remove)
        run_scan([keep.pk, remove.pk])
        refresh_product_embeddings(Product.objects.filter(pk=keep.pk))
        messages.success(request, f"已将 {remove.sku} 合并到 {keep.sku}：迁移号码 {moved['numbers']} 个、适配 {moved['fitments']} 条、报价 {moved['offers']} 条")
        return redirect("catalog:detail", pk=keep.pk)
    return render(request, "quality/merge.html", {"a": a, "b": b, "pair": [a, b]})


def fill(request, pk):
    product = get_object_or_404(product_detail_queryset(), pk=pk)
    if request.method == "POST":
        values = {k: request.POST.get(k, "") for k in fixes.FILLABLE if request.POST.get(f"accept_{k}")}
        changed = fixes.accept_suggestions(product, values)
        if changed:
            run_scan([product.pk])
            refresh_product_embeddings(Product.objects.filter(pk=product.pk))
        response = render(request, "quality/_fill_done.html", {"changed": changed})
        response["HX-Refresh"] = "true"
        return response
    try:
        suggestions = fixes.suggest_missing(product)
        error = ""
    except AIError as exc:
        suggestions, error = {}, str(exc)
    return render(request, "quality/_fill.html", {"product": product, "suggestions": suggestions, "error": error})

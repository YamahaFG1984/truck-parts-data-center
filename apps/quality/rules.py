"""Data quality rules (PRD §6.3, DESIGN.md §7.1). Add a rule = add a decorated function."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from rapidfuzz import fuzz

from apps.catalog.models import PartNumber

RULES = []
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
CJK = re.compile(r"[一-鿿]")
SPEC_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
UNIT_TEXT = re.compile(r"(mm\.?|毫米|cm|厘米)\s*$", re.I)
BAD_NUMBER = re.compile(r"[^A-Za-z0-9 .\-/]|\s{2,}|^\s|\s$")


@dataclass
class Rule:
    code: str
    category: str
    severity: str
    title: str
    fn: callable


@dataclass
class Issue:
    product_id: int
    field: str
    message: str
    related_product_id: int | None = None


def rule(code, category, severity, title):
    def register(fn):
        RULES.append(Rule(code, category, severity, title, fn))
        return fn
    return register


def rules_by_code():
    return {r.code: r for r in RULES}


@rule("MISSING_IMAGE", "missing", "high", "无产品图片")
def missing_image(products):
    return (Issue(p.id, "images", "没有产品图片") for p in products if not p.images.all())


@rule("MISSING_OE", "missing", "high", "无 OE 号")
def missing_oe(products):
    return (Issue(p.id, "part_numbers", "没有 OE 原厂号，客户按 OE 号询价时无法命中") for p in products if not p.oe_numbers)


@rule("MISSING_FITMENT", "missing", "medium", "无适配车型")
def missing_fitment(products):
    return (Issue(p.id, "fitments", "没有适配车型") for p in products if not p.fitments.all())


@rule("MISSING_PACKAGE", "missing", "medium", "缺重量或包装尺寸")
def missing_package(products):
    for p in products:
        missing = [label for label, v in [("重量", p.weight_kg), ("长", p.package_l_cm), ("宽", p.package_w_cm), ("高", p.package_h_cm), ("每包数量", p.qty_per_package)] if not v]
        if missing:
            yield Issue(p.id, "package", f"缺少：{'、'.join(missing)}")


@rule("MISSING_DESC_EN", "missing", "low", "无英文描述")
def missing_desc(products):
    return (Issue(p.id, "description_en", "英文描述为空或过短（<50 字符）") for p in products if len(p.description_en or "") < 50)


@rule("DUP_PART_NUMBER", "duplicate", "high", "同号码多个 SKU")
def duplicate_part_number(products):
    ids = {p.id for p in products}
    by_number = defaultdict(set)
    for pn in PartNumber.objects.filter(type__in=[PartNumber.OE, PartNumber.CROSS]).exclude(product__status="archived").values("normalized", "product_id"):
        by_number[pn["normalized"]].add(pn["product_id"])
    for number, owners in by_number.items():
        if len(owners) < 2:
            continue
        for pid in owners & ids:
            other = min(owners - {pid})
            yield Issue(pid, "part_numbers", f"号码 {number} 同时挂在 {len(owners)} 个 SKU 上，疑似重复", related_product_id=other)


@rule("DUP_SIMILAR_NAME", "duplicate", "medium", "疑似重复（名称规格相近）")
def duplicate_similar(products):
    groups = defaultdict(list)
    for p in products:
        if p.specs:
            make = p.oe_numbers[0].brand_id if p.oe_numbers else None
            groups[(p.category_id, make, str(sorted(p.specs.items())))].append(p)
    for items in groups.values():
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if fuzz.token_sort_ratio(a.name_en, b.name_en) >= 90 and {f.vehicle_model_id for f in a.fitments.all()} & {f.vehicle_model_id for f in b.fitments.all()}:
                    yield Issue(a.id, "name_en", f"与 {b.sku} 名称、规格、车型高度相似", related_product_id=b.id)
                    yield Issue(b.id, "name_en", f"与 {a.sku} 名称、规格、车型高度相似", related_product_id=a.id)


@rule("FMT_PART_NUMBER", "format", "low", "号码格式不规范")
def format_part_number(products):
    for p in products:
        for pn in p.part_numbers.all():
            if BAD_NUMBER.search(pn.number):
                yield Issue(p.id, "part_numbers", f"号码「{pn.number}」含多余空格或非法字符")


@rule("FMT_UNIT", "format", "low", "规格单位/键名不统一")
def format_unit(products):
    for p in products:
        bad = [k for k, v in (p.specs or {}).items() if not SPEC_KEY.match(k) or (isinstance(v, str) and UNIT_TEXT.search(v))]
        if bad:
            yield Issue(p.id, "specs", f"规格 {', '.join(bad)} 未按「英文键_单位: 数值」规范")


@rule("FMT_NAME_EN_CJK", "format", "medium", "英文名含中文")
def format_name_cjk(products):
    return (Issue(p.id, "name_en", f"英文名「{p.name_en}」含中文字符") for p in products if CJK.search(p.name_en or ""))


@rule("STALE_OFFER", "consistency", "low", "报价过期")
def stale_offer(products):
    limit = date.today() - timedelta(days=settings.OFFER_FRESH_DAYS)
    for p in products:
        offers = p.offers.all()
        if offers:
            latest = max(o.quoted_at for o in offers)
            if latest < limit:
                yield Issue(p.id, "offers", f"最新报价日期 {latest}，已超过 {settings.OFFER_FRESH_DAYS} 天")


@rule("NO_OFFER", "consistency", "medium", "无供应商报价")
def no_offer(products):
    return (Issue(p.id, "offers", "没有任何供应商报价，无法快速报价") for p in products if not p.offers.all())

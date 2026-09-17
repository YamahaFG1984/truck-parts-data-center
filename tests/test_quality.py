from apps.catalog.models import PartNumber, Product
from apps.quality import fixes
from apps.quality.models import DataIssue
from apps.quality.scan import run_scan
from apps.quality.scoring import completeness


def codes(product):
    return set(DataIssue.objects.filter(product=product, resolved=False).values_list("rule_code", flat=True))


def test_scan_finds_missing_data(catalog):
    run_scan()
    spring = catalog["spring"]
    assert {"MISSING_IMAGE", "MISSING_PACKAGE", "MISSING_DESC_EN", "NO_OFFER"} <= codes(spring)
    assert "MISSING_OE" not in codes(spring)
    assert "STALE_OFFER" not in codes(catalog["pad"])  # has a fresh offer


def test_duplicate_part_number_detected_and_merged(catalog):
    dup = Product.objects.create(sku="FIT-00009", name_en="Brake Pad Kit", category=catalog["pads"])
    PartNumber.objects.create(product=dup, number="81 50804 6004", type=PartNumber.OE)
    run_scan()
    issue = DataIssue.objects.get(product=dup, rule_code="DUP_PART_NUMBER")
    assert issue.related_product_id == catalog["pad"].id

    fixes.merge_products(catalog["pad"], dup)
    run_scan()
    dup.refresh_from_db()
    assert dup.status == Product.ARCHIVED and dup.merged_into_id == catalog["pad"].id
    assert not DataIssue.objects.filter(rule_code="DUP_PART_NUMBER", resolved=False).exists()
    assert catalog["pad"].part_numbers.filter(normalized="81508046004").count() == 1


def test_completeness_score(catalog):
    pad = Product.objects.prefetch_related("images", "part_numbers", "fitments", "offers").get(pk=catalog["pad"].pk)
    score, parts = completeness(pad)
    # no image and no logistics data in the fixture
    assert parts["图片"] == 0 and parts["OE号"] == 20 and parts["Cross号"] == 5 and parts["供应商报价"] == 10
    assert score == sum(parts.values())


def test_fix_units(catalog):
    p = catalog["pad2"]
    p.specs = {"直径(MM)": "430 MM", "Thickness（毫米）": "45毫米", "holes": 10}
    p.save()
    run_scan([p.id])
    assert "FMT_UNIT" in codes(p)
    assert fixes.fix_units(Product.objects.filter(pk=p.pk)) == 1
    p.refresh_from_db()
    assert p.specs == {"diameter_mm": 430, "thickness_mm": 45, "holes": 10}
    run_scan([p.id])
    assert "FMT_UNIT" not in codes(p)


def test_ai_fill_only_suggests_text_fields(catalog):
    spring = Product.objects.get(pk=catalog["spring"].pk)
    suggestions = fixes.suggest_missing(spring)
    assert set(suggestions) == {"description_en"}
    fixes.accept_suggestions(spring, {"description_en": suggestions["description_en"]["value"], "weight_kg": "99"})
    spring.refresh_from_db()
    assert len(spring.description_en) >= 50 and spring.weight_kg is None

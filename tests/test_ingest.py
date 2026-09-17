from datetime import date

from django.core.files.base import ContentFile
from openpyxl import Workbook

from apps.catalog.models import PartNumber
from apps.ingest import services
from apps.ingest.extract import infer_currency, map_columns, transform_row
from apps.ingest.models import ImportBatch, ImportRow
from apps.ingest.readers import read_excel
from apps.ingest.tasks import process_batch


def make_excel(path, rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_header_row_detected_below_title(tmp_path):
    path = make_excel(tmp_path / "a.xlsx", [["某某厂报价单"], [], ["货号", "品名", "原厂号", "单价(元)"], ["HD-1", "刹车片", "20837792", 88]])
    sheet = read_excel(path)
    assert sheet.headers == ["货号", "品名", "原厂号", "单价(元)"]
    assert sheet.rows[0][1]["原厂号"] == "20837792"


def test_mock_column_mapping_chinese_and_english(db):
    assert map_columns(["货号", "原厂号", "参考号", "单价(元)", "起订量", "交期(天)"], []) == {
        "货号": "supplier_part_no", "原厂号": "oe_numbers", "参考号": "cross_numbers",
        "单价(元)": "cost_price", "起订量": "moq", "交期(天)": "lead_time_days",
    }
    mapping = map_columns(["Item No.", "OEM No.", "FOB Price (USD)", "Lead Time"], [])
    assert mapping["OEM No."] == "oe_numbers" and infer_currency(mapping) == "USD"


def test_transform_row_parses_values():
    mapping = {"OE": "oe_numbers", "Price": "cost_price", "Lead": "lead_time_days"}
    row, errors = transform_row({"OE": "20837792 / 21122012", "Price": "¥1,280.50", "Lead": "15 days"}, mapping, "CNY")
    assert row["oe_numbers"] == ["20837792", "21122012"]
    assert row["cost_price"] == 1280.5 and row["lead_time_days"] == 15 and row["currency"] == "CNY"
    assert errors == []


def test_process_and_approve_batch(catalog, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    path = make_excel(tmp_path / "s.xlsx", [
        ["货号", "品名", "原厂号", "参考号", "单价(元)", "起订量"],
        ["HD-1", "刹车片", "81508046004", "KNORR K999888", 95, 20],
        ["HD-2", "刹车片 新款", "99911122", "", 120, 50],
    ])
    batch = ImportBatch.objects.create(supplier=catalog["supplier"], file_type="xlsx")
    batch.file.save("s.xlsx", ContentFile(path.read_bytes()))
    process_batch(batch.pk)
    batch.refresh_from_db()
    assert batch.status == ImportBatch.REVIEWING and batch.stats["total"] == 2

    matched = batch.rows.get(row_index=2)
    assert matched.matched_product_id == catalog["pad"].id and matched.confidence == 100 and matched.preselected
    services.approve(matched)
    cross = catalog["pad"].part_numbers.get(normalized="K999888")
    assert cross.type == PartNumber.CROSS and cross.brand == catalog["knorr"]
    assert catalog["pad"].offers.filter(supplier_part_no="HD-1", cost_price=95, quoted_at=date.today()).exists()

    new = batch.rows.get(row_index=3)
    product = services.create_product(new)
    assert product.status == "draft" and product.category == catalog["pads"]
    assert product.part_numbers.filter(normalized="99911122", type=PartNumber.OE).exists()

    services.refresh_batch(batch, {catalog["pad"].id, product.id})
    batch.refresh_from_db()
    assert batch.status == ImportBatch.DONE and batch.stats["pending"] == 0
    assert set(batch.rows.values_list("status", flat=True)) == {ImportRow.APPROVED, ImportRow.NEW_PRODUCT}

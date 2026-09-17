"""Background processing of an uploaded supplier file (runs in the django-q2 worker)."""

import traceback
from pathlib import Path

from .extract import extract_pdf_text, infer_currency, map_columns, match_row, transform_row, AUTO_APPROVE_SCORE
from .models import ImportBatch, ImportRow
from .readers import read_file


def process_batch(batch_id: int) -> dict:
    batch = ImportBatch.objects.get(pk=batch_id)
    batch.status = ImportBatch.PARSING
    batch.rows.all().delete()
    batch.log = ""
    batch.add_log("开始读取文件")
    batch.save()
    try:
        sheet = read_file(Path(batch.file.path))
        batch.add_log(f"读取到 {len(sheet.rows)} 行表格数据，{len(sheet.text_chunks)} 段非表格文本")

        extracted: list[tuple[int, dict, dict, list]] = []
        if sheet.rows:
            mapping = map_columns(sheet.headers, [r for _, r in sheet.rows])
            batch.column_mapping = mapping
            currency = infer_currency(mapping)
            batch.add_log(f"AI 列映射完成：{len(mapping)}/{len(sheet.headers)} 列已识别，默认币种 {currency}")
            for row_no, raw in sheet.rows:
                row, errors = transform_row(raw, mapping, currency)
                extracted.append((row_no, raw, row, errors))
        for i, chunk in enumerate(sheet.text_chunks):
            for j, row in enumerate(extract_pdf_text(chunk)):
                extracted.append((10000 + i * 100 + j, {"text": chunk[:500]}, row, []))

        batch.stats = {"total": len(extracted), "processed": 0}
        batch.save()
        matched = 0
        for n, (row_no, raw, row, errors) in enumerate(extracted, 1):
            best = match_row(row) if not errors or row.get("oe_numbers") or row.get("cross_numbers") else None
            ImportRow.objects.create(
                batch=batch, row_index=row_no, raw={k: (str(v) if v is not None else None) for k, v in raw.items()},
                extracted=row, errors=errors,
                matched_product_id=best.product_id if best else None,
                match_method=best.method if best else "", confidence=best.score if best else 0,
                preselected=bool(best and best.score >= AUTO_APPROVE_SCORE and not errors),
            )
            matched += bool(best and best.score >= 80)
            if n % 5 == 0:
                batch.stats["processed"] = n
                batch.save(update_fields=["stats"])
        batch.stats.update({"processed": len(extracted), "matched": matched, "unmatched": len(extracted) - matched, "pending": len(extracted)})
        batch.status = ImportBatch.REVIEWING
        batch.add_log(f"匹配完成：{matched} 行匹配到已有 SKU（置信度≥80），{len(extracted) - matched} 行需人工判断/新建")
    except Exception as exc:
        batch.status = ImportBatch.FAILED
        batch.add_log(f"处理失败：{exc}\n{traceback.format_exc()[-1500:]}")
    batch.save()
    return batch.stats

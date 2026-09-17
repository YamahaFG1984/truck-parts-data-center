"""Read supplier files into headers + row dicts (DESIGN.md §9 step 1)."""

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber


@dataclass
class Sheet:
    headers: list[str] = field(default_factory=list)
    rows: list[tuple[int, dict]] = field(default_factory=list)  # (source row number, {header: value})
    text_chunks: list[str] = field(default_factory=list)  # PDF pages without tables


def _clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _header_row(frame: pd.DataFrame) -> int:
    """Suppliers put titles and contacts above the table: the header is the densest of the first rows."""
    head = frame.head(10)
    counts = head.notna().sum(axis=1)
    return int(counts.idxmax())


def read_excel(path: Path) -> Sheet:
    frame = pd.read_excel(path, header=None, dtype=object)
    frame = frame.dropna(how="all").dropna(axis=1, how="all")
    header_idx = _header_row(frame)
    headers = [str(_clean(h) or f"列{i + 1}") for i, h in enumerate(frame.loc[header_idx])]
    sheet = Sheet(headers=headers)
    for idx, values in frame.loc[header_idx + 1 :].iterrows():
        row = {h: _clean(v) for h, v in zip(headers, values)}
        if any(v is not None for v in row.values()):
            sheet.rows.append((int(idx) + 1, row))
    return sheet


def read_pdf(path: Path) -> Sheet:
    sheet = Sheet()
    row_no = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                text = page.extract_text() or ""
                if text.strip():
                    sheet.text_chunks.append(text)
                continue
            for table in tables:
                if not table:
                    continue
                start = 0
                if not sheet.headers:
                    sheet.headers = [str(_clean(h) or f"列{i + 1}") for i, h in enumerate(table[0])]
                    start = 1
                elif [str(_clean(h)) for h in table[0]] == sheet.headers:
                    start = 1  # header repeated on every page
                for values in table[start:]:
                    row_no += 1
                    row = {h: _clean(v) for h, v in zip(sheet.headers, values)}
                    if any(v is not None for v in row.values()):
                        sheet.rows.append((row_no, row))
    return sheet


def read_file(path: Path) -> Sheet:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return read_excel(path)
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=object)
        sheet = Sheet(headers=[str(h) for h in frame.columns])
        for idx, values in frame.iterrows():
            sheet.rows.append((int(idx) + 2, {h: _clean(v) for h, v in zip(sheet.headers, values)}))
        return sheet
    raise ValueError(f"不支持的文件类型：{suffix}")

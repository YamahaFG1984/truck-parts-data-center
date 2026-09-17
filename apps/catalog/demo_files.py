"""Demo supplier price lists, catalog PDF, customer photos and sample inquiries.

They are generated from the seeded catalog so that the ingest and inquiry demos
hit exact, fuzzy, cross-reference and "new product" cases deterministically.
"""

import json
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.catalog import demo
from apps.catalog.images import draw_part_image
from apps.catalog.models import PartNumber, Product


def _products(codes, n):
    qs = (Product.objects.filter(category__name_en__in=codes, status=Product.ACTIVE, part_numbers__type=PartNumber.OE)
          .distinct().prefetch_related("part_numbers__brand", "fitments__vehicle_model").order_by("sku"))
    items = list(qs)
    random.shuffle(items)
    return items[:n]


def _typo(number: str) -> str:
    """Change one digit in the middle: the kind of mistake customers make."""
    digits = [i for i, c in enumerate(number) if c.isdigit()]
    i = digits[len(digits) // 2]
    return number[:i] + str((int(number[i]) + 3) % 10) + number[i + 1:]


def _vehicle_text(p):
    return ", ".join(str(f.vehicle_model).split(" (")[0] for f in p.fitments.all())


def write_supplier_cn(path: Path, brands):
    """Chinese headers, title rows above the header, numbers without separators."""
    wb = Workbook()
    ws = wb.active
    ws.title = "报价单"
    ws.append(["瑞安恒达制动配件厂（演示） 2026年9月 出厂报价单"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["联系人：王经理  电话：0577-00000000  （价格含税，人民币）"])
    ws.append(["货号", "品名", "原厂号", "参考号", "适用车型", "规格", "单价(元)", "起订量", "交期(天)", "包装方式", "净重kg"])
    idx = 100
    used = set()
    for p in _products(["Brake Pad Set", "Brake Disc", "Brake Drum"], 14):
        used.add(p.id)
        idx += 1
        oe = p.oe_numbers[0].number if p.oe_numbers else ""
        new_cross = demo.CROSS_FORMATS["Knorr-Bremse"]()
        specs = "*".join(str(v) for v in p.specs.values() if isinstance(v, (int, float))) if isinstance(p.specs, dict) else ""
        ws.append([f"HD-{idx}", p.name_cn, oe.replace(" ", "").replace(".", "").replace("-", "") if idx % 2 else oe,
                   f"KNORR {new_cross}", _vehicle_text(p), f"{specs}mm" if specs else "", round(random.uniform(90, 650), 1),
                   random.choice([20, 50, 100]), random.choice([15, 25, 30]), "中性彩盒", float(p.weight_kg or 0) or None])
    # Matched only through an existing cross reference number.
    with_cross = [p for p in _products(["Brake Pad Set", "Brake Disc"], 40) if p.cross_numbers and p.id not in used][:3]
    for p in with_cross:
        idx += 1
        cross = p.cross_numbers[0]
        ws.append([f"HD-{idx}", p.name_cn, "", f"{cross.brand.name} {cross.number}", _vehicle_text(p), "", round(random.uniform(90, 650), 1), 50, 30, "白盒+纸箱", None])
    # New parts we do not have yet.
    for name, make in [("刹车片 前轮", "Volvo"), ("刹车盘 后轮", "Scania"), ("刹车鼓", "MAN"), ("刹车片 带报警线", "DAF")]:
        idx += 1
        ws.append([f"HD-{idx}", name, demo.OE_FORMATS[make](), "", f"{make} 新款", "", round(random.uniform(90, 650), 1), 50, 30, "中性彩盒", None])
    wb.save(path)


def write_supplier_en(path: Path):
    """English headers in a different order, USD prices, one typo in an OE number."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Price List"
    ws.append(["Item No.", "OEM No.", "Description", "FOB Price (USD)", "Cross Ref.", "MOQ", "Lead Time", "Packing", "N.W. (kg)"])
    for i, p in enumerate(_products(["Oil Filter", "Air Filter"], 14)):
        oe = p.oe_numbers[0].number
        cross = "; ".join(f"{n.brand.name} {n.number}" for n in p.cross_numbers[:2])
        ws.append([f"XY-{2000 + i}", _typo(oe) if i == 3 else oe, p.name_en, round(random.uniform(3, 30), 2), cross,
                   random.choice([50, 100, 200]), f"{random.choice([15, 20, 30])} days", "Neutral box", float(p.weight_kg or 0) or None])
    for i, make in enumerate(["Iveco", "Renault", "Volvo"]):
        ws.append([f"XY-{2100 + i}", demo.OE_FORMATS[make](), random.choice(["Oil Filter Element", "Air Filter Primary"]),
                   round(random.uniform(3, 30), 2), "", 100, "25 days", "Neutral box", None])
    wb.save(path)


def write_supplier_pdf(path: Path):
    styles = getSampleStyleSheet()
    rows = [["Item No.", "Product", "OE No.", "Ref. No.", "Price (CNY)", "MOQ", "Lead Time"]]
    for i, p in enumerate(_products(["Air Spring", "Shock Absorber"], 12)):
        cross = p.cross_numbers[0] if p.cross_numbers else None
        rows.append([f"BY-{300 + i}", p.name_en, " / ".join(n.number for n in p.oe_numbers[:2]),
                     f"{cross.brand.name} {cross.number}" if cross else "", f"{random.uniform(280, 650):.0f}", "20", "30 days"])
    rows.append(["BY-399", "Cabin Air Spring", demo.OE_FORMATS["DAF"](), "", "320", "20", "30 days"])
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4))
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    doc.build([Paragraph("Hebei Boyuan Suspension Parts (DEMO) - Product Catalog 2026", styles["Title"]), Spacer(1, 12), table])


def write_photos(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    pad = _products(["Brake Pad Set"], 1)[0]
    oe = pad.oe_numbers[0]
    draw_part_image(directory / "customer_photo_brake_pad.png", "brake_pad", "photo from customer", f"label: {oe.number}", photo=True, demo_label={
        "part_type": "brake pad set", "part_type_cn": "刹车片", "visible_numbers": [oe.number], "brand": None,
        "features": ["two pads", "wear indicator clip"], "description": f"disc brake pad set for {oe.brand.name} truck",
    })
    draw_part_image(directory / "customer_photo_air_spring.png", "air_spring", "photo from customer", "no label", photo=True, demo_label={
        "part_type": "air spring", "part_type_cn": "空气弹簧", "visible_numbers": [], "brand": None,
        "features": ["rolling lobe", "steel piston"], "description": "rear axle air spring for Volvo FH truck",
    })


def write_inquiries(path: Path):
    pads = _products(["Brake Pad Set", "Brake Disc"], 2)
    exact = pads[0].oe_numbers[0].number
    typo_src = pads[1].oe_numbers[0].number
    filters = _products(["Oil Filter", "Air Filter"], 2)
    crosses = [n for f in filters for n in f.cross_numbers][:2]
    samples = [
        {
            "title": "邮件询价：精确号 + 写错的号 + 只有描述",
            "customer": "Nordic Fleet Service AB",
            "channel": "email",
            "text": (
                "Dear Sales,\n\nPlease quote your best price for the following:\n"
                f"1. OE {exact.replace(' ', '-') if ' ' in exact else exact} - 20 pcs\n"
                f"2. {_typo(typo_src)} qty 10\n"
                "3. Rear axle air spring for Volvo FH, 6 pcs\n\n"
                "Best regards,\nErik Johansson\nNordic Fleet Service AB"
            ),
        },
        {
            "title": "WhatsApp：竞品 Cross 号询价",
            "customer": "Lagos Truck Parts Ltd",
            "channel": "whatsapp",
            "text": "Hi, need price for\n" + "\n".join(f"{n.brand.name} {n.number} x 50" for n in crosses) + "\nThanks",
        },
        {
            "title": "Alibaba 询盘：只有描述和车型",
            "customer": "Andes Heavy Equipment",
            "channel": "alibaba",
            "text": "Hello, we are looking for front brake disc for Scania R-series 430mm, 20 pcs.\nAlso cabin shock absorber for MAN TGX, 10 pcs.\nPlease send catalog.",
        },
    ]
    path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")


def write_all(directory: Path, brands, suppliers):
    write_supplier_cn(directory / "供应商报价_恒达制动.xlsx", brands)
    write_supplier_en(directory / "supplier_pricelist_xinyuan_filters.xlsx")
    write_supplier_pdf(directory / "supplier_catalog_boyuan_suspension.pdf")
    write_photos(directory / "inquiry_photos")
    write_inquiries(directory / "sample_inquiries.json")

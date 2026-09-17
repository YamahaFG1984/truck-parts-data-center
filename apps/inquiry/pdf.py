from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def quotation_pdf(inquiry, items) -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Quotation Q{inquiry.pk:05d}")
    rows = [["#", "Our SKU", "Your Ref.", "Description", "Qty", "Unit USD", "Amount USD"]]
    total = 0
    for i, it in enumerate(items, 1):
        rows.append([i, it["sku"], Paragraph(it["requested"][:40], styles["BodyText"]), Paragraph(it["name"], styles["BodyText"]),
                     it["qty"], it["unit_price"], it["subtotal"]])
        total += float(it["subtotal"])
    rows.append(["", "", "", "", "", "Total", f"{total:.2f}"])
    table = Table(rows, colWidths=[20, 70, 90, 150, 35, 60, 70], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -2), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    doc.build([
        Paragraph("QUOTATION (DEMO)", styles["Title"]),
        Paragraph(f"No. Q{inquiry.pk:05d} &nbsp;&nbsp; Date: {inquiry.updated_at:%Y-%m-%d} &nbsp;&nbsp; To: {inquiry.customer or 'Customer'}", styles["Normal"]),
        Spacer(1, 12), table, Spacer(1, 12),
        Paragraph("Terms: FOB China · Price validity 15 days · Payment T/T 30% deposit · Warranty 12 months.", styles["Normal"]),
        Paragraph("Alternative parts are cross-referenced by OE number and equivalent in fitment.", styles["Normal"]),
    ])
    return buffer.getvalue()

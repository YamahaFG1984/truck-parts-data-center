"""Completeness score 0-100 (DESIGN.md §7.2)."""


def completeness(p) -> tuple[int, dict]:
    package_fields = [p.weight_kg, p.package_l_cm, p.package_w_cm, p.package_h_cm, p.qty_per_package]
    spec_count = len(p.specs or {})
    parts = {
        "图片": 20 if p.images.all() else 0,
        "OE号": 20 if p.oe_numbers else 0,
        "适配车型": 15 if p.fitments.all() else 0,
        "规格": 10 if spec_count >= 2 else (5 if spec_count == 1 else 0),
        "包装物流": round(10 * sum(1 for v in package_fields if v) / len(package_fields)),
        "英文描述": 10 if len(p.description_en or "") >= 50 else 0,
        "Cross号": 5 if p.cross_numbers else 0,
        "供应商报价": 10 if p.offers.all() else 0,
    }
    return sum(parts.values()), parts


WEIGHTS = {"图片": 20, "OE号": 20, "适配车型": 15, "规格": 10, "包装物流": 10, "英文描述": 10, "Cross号": 5, "供应商报价": 10}

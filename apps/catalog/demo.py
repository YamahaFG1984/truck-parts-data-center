"""Reference data and generators for the synthetic demo dataset.

All part numbers are FICTIONAL, generated to look like each brand's real
format so that normalisation and matching can be demonstrated.
"""

import random

OEM_BRANDS = ["Volvo", "Scania", "MAN", "Mercedes-Benz", "DAF", "Iveco", "Renault"]
MAKE_CN = {"Volvo": "沃尔沃", "Scania": "斯堪尼亚", "MAN": "曼", "Mercedes-Benz": "奔驰", "DAF": "达夫", "Iveco": "依维柯", "Renault": "雷诺"}

VEHICLES = {
    "Volvo": [("FH12", 1993, 2005, "D12"), ("FH (2nd gen)", 2002, 2012, "D13A"), ("FH4", 2012, 2020, "D13K"), ("FH5", 2020, None, "D13K"), ("FM", 2005, 2013, "D11A"), ("FMX", 2010, None, "D13")],
    "Scania": [("R-series", 2004, 2016, "DC13"), ("P/G-series", 2004, 2016, "DC9"), ("S-series", 2016, None, "DC13"), ("4-series", 1995, 2004, "DC12")],
    "MAN": [("TGA", 2000, 2013, "D2066"), ("TGX", 2007, None, "D2676"), ("TGS", 2007, None, "D2066"), ("TGL", 2005, None, "D0834"), ("TGM", 2005, None, "D0836")],
    "Mercedes-Benz": [("Actros MP2", 2002, 2008, "OM501LA"), ("Actros MP4", 2011, 2019, "OM471"), ("Axor", 2001, 2013, "OM457LA"), ("Atego", 1998, None, "OM906LA"), ("Arocs", 2013, None, "OM470")],
    "DAF": [("XF95", 2002, 2006, "MX340"), ("XF105", 2005, 2013, "MX340"), ("XF106", 2013, None, "MX-13"), ("CF85", 2001, 2013, "MX340"), ("LF45", 2001, 2013, "FR136")],
    "Iveco": [("Stralis", 2002, 2016, "Cursor 10"), ("Eurocargo", 2003, None, "Tector"), ("Trakker", 2004, None, "Cursor 13"), ("S-Way", 2019, None, "Cursor 13")],
    "Renault": [("Magnum", 2001, 2013, "DXi12"), ("Premium", 1996, 2013, "DXi11"), ("T-series", 2013, None, "DTI13"), ("K-series", 2013, None, "DTI13"), ("D-series", 2013, None, "DTI8")],
}


def _d(n):
    return "".join(random.choice("0123456789") for _ in range(n))


OE_FORMATS = {
    "Volvo": lambda: random.choice(["20", "21", "22", "85"]) + _d(6),
    "Scania": lambda: random.choice(["1", "2"]) + _d(6),
    "MAN": lambda: f"81.{_d(5)}-{_d(4)}",
    "Mercedes-Benz": lambda: f"A {_d(3)} {_d(3)} {_d(2)} {_d(2)}",
    "DAF": lambda: random.choice(["1", "2"]) + _d(6),
    "Iveco": lambda: random.choice(["42", "50", "41"]) + _d(6),
    "Renault": lambda: f"50{_d(2)} {_d(3)} {_d(3)}",
}

CROSS_FORMATS = {
    "Knorr-Bremse": lambda: f"K{_d(6)}",
    "Textar": lambda: f"29{_d(3)}",
    "Jurid": lambda: f"2915{_d(3)}",
    "TRW": lambda: f"DF{_d(4)}",
    "Febi": lambda: f"{_d(5)}",
    "MANN-FILTER": lambda: random.choice([f"W {_d(3)}/{_d(2)}", f"C {_d(2)} {_d(3)}", f"HU {_d(2)} {_d(3)} x"]),
    "Fleetguard": lambda: random.choice(["LF", "AF", "FF"]) + _d(5),
    "Donaldson": lambda: f"P{_d(6)}",
    "Firestone": lambda: f"W01-358 {_d(4)}",
    "ContiTech": lambda: f"{_d(4)} NP {_d(2)}",
    "Sachs": lambda: f"{_d(3)} {_d(3)}",
    "Monroe": lambda: f"T{_d(4)}",
    "Valeo": lambda: f"8{_d(5)}",
}

# code: (parent_cn, name_cn, name_en, margin, cross brands, cost CNY range, weight kg range, variants, spec generator)
CATEGORIES = [
    ("brake_pad", "制动系统", "刹车片", "Brake Pad Set", 0.35, ["Knorr-Bremse", "Textar", "Jurid"], (80, 260), (3.5, 8),
     ["Front", "Rear", "Disc"],
     lambda: {"length_mm": random.randint(200, 255), "width_mm": random.randint(88, 112), "thickness_mm": random.choice([29, 30]), "wear_sensor": random.choice(["yes", "no"])}),
    ("brake_disc", "制动系统", "刹车盘", "Brake Disc", 0.30, ["Knorr-Bremse", "TRW", "Febi"], (250, 700), (28, 45),
     ["Front", "Rear", "Ventilated"],
     lambda: {"diameter_mm": random.choice([410, 430, 432]), "thickness_mm": random.randint(34, 48), "height_mm": random.randint(120, 170), "bolt_holes": random.choice([10, 12, 13])}),
    ("brake_drum", "制动系统", "刹车鼓", "Brake Drum", 0.28, ["TRW", "Febi"], (300, 800), (40, 75),
     ["Front", "Rear"],
     lambda: {"diameter_mm": random.choice([410, 420]), "width_mm": random.randint(160, 230), "height_mm": random.randint(180, 260), "bolt_holes": 10}),
    ("oil_filter", "滤清器", "机油滤清器", "Oil Filter", 0.40, ["MANN-FILTER", "Fleetguard", "Donaldson"], (20, 80), (0.6, 1.8),
     ["Spin-on", "Element", "Bypass"],
     lambda: {"height_mm": random.randint(150, 310), "outer_diameter_mm": random.choice([93, 108, 118, 136]), "thread": random.choice(["M95x2.5", "1 1/8-16 UN", "M24x1.5"])}),
    ("air_filter", "滤清器", "空气滤清器", "Air Filter", 0.38, ["MANN-FILTER", "Fleetguard", "Donaldson"], (60, 220), (2.5, 6),
     ["Primary", "Safety", "Cabin"],
     lambda: {"height_mm": random.randint(400, 620), "outer_diameter_mm": random.choice([277, 308, 342]), "inner_diameter_mm": random.choice([178, 190, 209])}),
    ("air_spring", "悬挂系统", "空气弹簧", "Air Spring", 0.32, ["Firestone", "ContiTech"], (280, 650), (6, 14),
     ["Rear Axle", "Cabin", "Lift Axle"],
     lambda: {"max_height_mm": random.randint(400, 580), "min_height_mm": random.randint(170, 240), "piston": random.choice(["steel", "plastic"])}),
    ("shock_absorber", "悬挂系统", "减震器", "Shock Absorber", 0.30, ["Sachs", "Monroe"], (150, 380), (4, 9),
     ["Front", "Rear", "Cabin"],
     lambda: {"min_length_mm": random.randint(300, 440), "max_length_mm": random.randint(500, 700), "mounting": random.choice(["eye-eye", "pin-eye"])}),
    ("clutch_disc", "传动系统", "离合器片", "Clutch Disc", 0.33, ["Sachs", "Valeo"], (400, 1200), (6, 11),
     ["Organic", "Ceramic"],
     lambda: {"diameter_mm": random.choice([362, 400, 430]), "spline": random.choice(["10x44.5", "24x50.8", "10x50.8"]), "springs": random.choice([6, 8]), "thickness_mm": random.choice([10.2, 10.8, 11.4])}),
]

PARENT_EN = {"制动系统": "Brake System", "滤清器": "Filters", "悬挂系统": "Suspension", "传动系统": "Drivetrain"}

SUPPLIERS = [
    ("瑞安恒达制动配件厂（演示）", "浙江瑞安", "brake_pad,brake_disc,brake_drum", 4),
    ("温州鑫源滤清器有限公司（演示）", "浙江温州", "oil_filter,air_filter", 5),
    ("河北博远悬挂部件有限公司（演示）", "河北邢台", "air_spring,shock_absorber", 3),
    ("济南众力离合器厂（演示）", "山东济南", "clutch_disc,brake_disc", 4),
    ("广州泰联汽配贸易（演示）", "广东广州", "brake_pad,oil_filter,air_spring,shock_absorber,clutch_disc", 3),
]

DESCRIPTION_TEMPLATE = (
    "{name} for {make} heavy-duty trucks. Manufactured to OE specifications with strict quality control. "
    "Specifications: {specs}. Please check the OE number of your original part before ordering."
)

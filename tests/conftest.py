from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.catalog.models import Brand, Category, Fitment, PartNumber, Product, VehicleModel
from apps.suppliers.models import Supplier, SupplierOffer


@pytest.fixture(autouse=True)
def mock_ai(settings):
    settings.AI_MOCK = True
    settings.Q_CLUSTER = {**settings.Q_CLUSTER, "sync": True}


@pytest.fixture
def catalog(db):
    """A tiny catalog: two brake pads, one air spring, with OE and cross numbers."""
    parent = Category.objects.create(name="制动系统", name_en="Brake System")
    pads = Category.objects.create(name="刹车片", name_en="Brake Pad Set", parent=parent, margin_rate=Decimal("0.30"))
    springs = Category.objects.create(name="空气弹簧", name_en="Air Spring", parent=parent, margin_rate=Decimal("0.50"))
    volvo = Brand.objects.create(name="Volvo", type=Brand.OEM)
    man = Brand.objects.create(name="MAN", type=Brand.OEM)
    knorr = Brand.objects.create(name="Knorr-Bremse", type=Brand.AFTERMARKET)
    fh = VehicleModel.objects.create(make="Volvo", series="FH4", year_from=2012, year_to=2020)
    tgx = VehicleModel.objects.create(make="MAN", series="TGX", year_from=2007)

    pad = Product.objects.create(sku="FIT-00001", name_en="Front Brake Pad Set", name_cn="曼 TGX 刹车片", category=pads,
                                 specs={"length_mm": 250, "width_mm": 100}, description_en="x" * 60)
    PartNumber.objects.create(product=pad, number="81.50804-6004", type=PartNumber.OE, brand=man)
    PartNumber.objects.create(product=pad, number="K012345", type=PartNumber.CROSS, brand=knorr)
    Fitment.objects.create(product=pad, vehicle_model=tgx)

    pad2 = Product.objects.create(sku="FIT-00002", name_en="Rear Brake Pad Set", category=pads, specs={"length_mm": 210})
    PartNumber.objects.create(product=pad2, number="20837792", type=PartNumber.OE, brand=volvo)

    spring = Product.objects.create(sku="FIT-00003", name_en="Rear Axle Air Spring", name_cn="沃尔沃 FH4 空气弹簧", category=springs)
    PartNumber.objects.create(product=spring, number="21122012", type=PartNumber.OE, brand=volvo)
    Fitment.objects.create(product=spring, vehicle_model=fh)

    supplier = Supplier.objects.create(name="测试供应商")
    SupplierOffer.objects.create(supplier=supplier, product=pad, cost_price=Decimal("100"), currency="CNY", moq=10, lead_time_days=20, quoted_at=date.today() - timedelta(days=10))
    SupplierOffer.objects.create(supplier=supplier, product=pad, cost_price=Decimal("50"), currency="CNY", quoted_at=date.today() - timedelta(days=400))

    from apps.ai.embeddings import refresh_product_embeddings

    refresh_product_embeddings()
    return {"pad": pad, "pad2": pad2, "spring": spring, "supplier": supplier, "knorr": knorr, "volvo": volvo, "pads": pads}

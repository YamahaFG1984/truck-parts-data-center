"""Build the synthetic demo dataset (PRD §7).

python manage.py seed_demo            # wipe business data and rebuild
"""

import random
import shutil
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command
from django.db import transaction

from apps.ai.client import PROMPT_DIR
from apps.ai.models import AICallLog, PromptTemplate
from apps.catalog import demo
from apps.catalog.images import draw_part_image
from apps.catalog.models import Brand, Category, Fitment, PartNumber, Product, ProductImage, VehicleModel
from apps.ingest.models import ImportBatch
from apps.inquiry.models import Inquiry
from apps.listing.models import ListingContent
from apps.quality.models import DataIssue
from apps.suppliers.models import Supplier, SupplierOffer

DEMO_DIR = Path(settings.BASE_DIR) / "demo_data"
PRODUCTS_PER_CATEGORY = 36  # 8 categories -> 288 SKUs (+ duplicates)


class Command(BaseCommand):
    help = "Rebuild the synthetic demo dataset"

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--skip-post", action="store_true", help="skip embeddings and quality scan")

    def handle(self, *args, **opts):
        random.seed(opts["seed"])
        with transaction.atomic():
            self.wipe()
            self.seed_prompts()
            self.seed_reference()
            self.seed_products()
            self.inject_dirty_data()
            self.seed_offers()
        self.write_demo_files()
        self.ensure_admin()
        if not opts["skip_post"]:
            call_command("build_embeddings", all=True)
            call_command("run_quality_scan")
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Product.objects.count()} products, {PartNumber.objects.count()} part numbers, "
            f"{SupplierOffer.objects.count()} offers. Demo files in {DEMO_DIR}"
        ))

    # ------------------------------------------------------------------ setup
    def wipe(self):
        for model in (ListingContent, DataIssue, Inquiry, ImportBatch, SupplierOffer, Supplier, Product, VehicleModel, Brand, Category, AICallLog):
            model.objects.all().delete()
        for folder in ("products", "imports", "inquiries"):
            shutil.rmtree(Path(settings.MEDIA_ROOT) / folder, ignore_errors=True)

    def seed_prompts(self):
        for path in sorted(PROMPT_DIR.glob("*.txt")):
            # v1 always mirrors the file in apps/ai/prompts; tuned versions (v2+) made in admin are kept.
            PromptTemplate.objects.update_or_create(code=path.stem, version=1, defaults={"content": path.read_text(encoding="utf-8"), "note": "默认模板"})

    def seed_reference(self):
        self.brands = {name: Brand.objects.create(name=name, type=Brand.OEM) for name in demo.OEM_BRANDS}
        for name in demo.CROSS_FORMATS:
            self.brands[name] = Brand.objects.create(name=name, type=Brand.AFTERMARKET)
        self.vehicles = {make: [VehicleModel.objects.create(make=make, series=s, year_from=f, year_to=t, engine=e) for s, f, t, e in rows]
                         for make, rows in demo.VEHICLES.items()}
        parents = {}
        self.categories = {}
        for code, parent_cn, name_cn, name_en, margin, *_ in demo.CATEGORIES:
            if parent_cn not in parents:
                parents[parent_cn] = Category.objects.create(name=parent_cn, name_en=demo.PARENT_EN[parent_cn])
            self.categories[code] = Category.objects.create(name=name_cn, name_en=name_en, parent=parents[parent_cn], margin_rate=Decimal(str(margin)))
        self.suppliers = [Supplier.objects.create(name=n, region=r, product_lines=lines, rating=rating, contact="sales@example.com")
                          for n, r, lines, rating in demo.SUPPLIERS]

    def _unique_number(self, fn):
        while True:
            n = fn()
            if n not in self.used_numbers:
                self.used_numbers.add(n)
                return n

    def seed_products(self):
        self.used_numbers = set()
        self.meta = {}  # product id -> category row
        counter = 0
        for row in demo.CATEGORIES:
            code, _, name_cn, name_en, _, cross_brands, _, weight, variants, spec_fn = row
            for _ in range(PRODUCTS_PER_CATEGORY):
                counter += 1
                make = random.choice(demo.OEM_BRANDS)
                variant = random.choice(variants)
                models = random.sample(self.vehicles[make], k=min(len(self.vehicles[make]), random.randint(1, 3)))
                series = models[0].series
                specs = spec_fn()
                name = f"{variant} {name_en}"
                product = Product.objects.create(
                    sku=f"FIT-{counter:05d}",
                    name_en=name,
                    name_cn=f"{demo.MAKE_CN[make]} {series} {name_cn}",
                    category=self.categories[code],
                    specs=specs,
                    weight_kg=Decimal(str(round(random.uniform(*weight), 2))),
                    package_l_cm=Decimal(random.randint(20, 60)), package_w_cm=Decimal(random.randint(15, 50)), package_h_cm=Decimal(random.randint(8, 40)),
                    qty_per_package=random.choice([1, 1, 1, 2, 4]) if code != "brake_pad" else 1,
                    description_en=demo.DESCRIPTION_TEMPLATE.format(
                        name=name, make=f"{make} {', '.join(m.series for m in models)}",
                        specs=", ".join(f"{k.replace('_', ' ')} {v}" for k, v in specs.items())),
                )
                self.meta[product.id] = row
                for _ in range(random.choice([1, 1, 2, 3])):
                    PartNumber.objects.create(product=product, number=self._unique_number(demo.OE_FORMATS[make]), type=PartNumber.OE, brand=self.brands[make])
                if make in ("Volvo", "Renault") and random.random() < 0.3:  # shared platform parts
                    other = "Renault" if make == "Volvo" else "Volvo"
                    PartNumber.objects.create(product=product, number=self._unique_number(demo.OE_FORMATS[other]), type=PartNumber.OE, brand=self.brands[other])
                for brand in random.sample(cross_brands, k=random.randint(1, len(cross_brands))):
                    PartNumber.objects.create(product=product, number=self._unique_number(demo.CROSS_FORMATS[brand]), type=PartNumber.CROSS, brand=self.brands[brand])
                for vm in models:
                    Fitment.objects.create(product=product, vehicle_model=vm)
                self._image(product, code)

    def _image(self, product, code):
        rel = f"products/{product.sku}.png"
        oe = product.part_numbers.filter(type=PartNumber.OE).first()
        draw_part_image(Path(settings.MEDIA_ROOT) / rel, code, product.name_en, oe.number if oe else product.sku)
        ProductImage.objects.create(product=product, image=rel, is_primary=True)

    def inject_dirty_data(self):
        """Realistic gaps for the quality dashboard (PRD §7).

        Each problem is sampled independently, so like real data many SKUs have
        several gaps at once and the average completeness lands around 70.
        """
        products = list(Product.objects.all())

        def sample(ratio):
            return random.sample(products, k=round(len(products) * ratio))

        for p in sample(0.35):  # no image
            p.images.all().delete()
        for p in sample(0.08):  # only cross numbers known
            p.part_numbers.filter(type=PartNumber.OE).delete()
        for p in sample(0.30):  # cross references never collected
            p.part_numbers.filter(type=PartNumber.CROSS).delete()
        for p in sample(0.22):  # no fitment
            p.fitments.all().delete()
        for p in sample(0.35):  # missing logistics data
            p.weight_kg = None
            p.package_l_cm = p.package_w_cm = p.package_h_cm = None
            p.save()
        for p in sample(0.50):  # no English description
            p.description_en = ""
            p.save()
        for p in sample(0.04):  # specs entered without convention
            p.specs = {}
            p.save()
        for p in sample(0.06):  # inconsistent units in specs
            if p.specs:
                p.specs = {
                    (k.replace("_mm", "").replace("_", " ").title() + random.choice(["(MM)", "", "（毫米）"])): (f"{v}{random.choice([' MM', '毫米', 'mm.'])}" if k.endswith("_mm") else v)
                    for k, v in p.specs.items()
                }
                p.save()
        for p in sample(0.03):  # messy raw part numbers
            pn = p.part_numbers.first()
            if pn:
                pn.number = f"  {pn.number[:3]}  {pn.number[3:]} "
                pn.save()
        for p in sample(0.015):  # Chinese in English name
            p.name_en = f"{p.name_en} {p.category.name}"
            p.save()
        # Duplicate SKUs: the same part entered twice by different colleagues.
        counter = len(products)
        for original in random.sample([p for p in products if p.part_numbers.exists()], k=6):
            counter += 1
            number = original.part_numbers.order_by("type").first()
            dup = Product.objects.create(
                sku=f"FIT-{counter:05d}", name_en=original.name_en.replace("Set", "Kit").replace("Disc", "Rotor"),
                name_cn=original.name_cn, category=original.category, specs=original.specs, qty_per_package=1,
            )
            self.meta[dup.id] = self.meta[original.id]
            PartNumber.objects.create(product=dup, number=number.number.replace(" ", "-") if " " in number.number else number.number,
                                      type=number.type, brand=number.brand)
        self.no_offer = {p.id for p in sample(0.10)}

    def seed_offers(self):
        today = date.today()
        for product in Product.objects.all():
            if product.id in self.no_offer:
                continue
            code, cost_range = self.meta[product.id][0], self.meta[product.id][6]
            candidates = [s for s in self.suppliers if code in s.product_lines]
            base = random.uniform(*cost_range)
            for supplier in random.sample(candidates, k=random.randint(1, len(candidates))):
                for _ in range(random.choice([1, 2, 2, 3])):
                    days_ago = random.choice([random.randint(5, 150), random.randint(5, 150), random.randint(190, 420)])
                    usd = random.random() < 0.15
                    cost = base * random.uniform(0.9, 1.15) * (0.14 if usd else 1)
                    SupplierOffer.objects.create(
                        supplier=supplier, product=product, supplier_part_no=f"{supplier.name[:2].upper()}-{random.randint(1000, 9999)}",
                        cost_price=Decimal(str(round(cost, 2))), currency="USD" if usd else "CNY",
                        moq=random.choice([10, 20, 50, 100]), lead_time_days=random.choice([7, 15, 25, 30, 45]),
                        packaging=random.choice(["中性彩盒", "白盒+纸箱", "Neutral box", "Customized box"]),
                        quoted_at=today - timedelta(days=days_ago),
                    )

    # ------------------------------------------------------------------ files
    def write_demo_files(self):
        DEMO_DIR.mkdir(exist_ok=True)
        from apps.catalog.demo_files import write_all

        write_all(DEMO_DIR, self.brands, self.suppliers)

    def ensure_admin(self):
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin123")

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.core.models import TimeStampedModel
from apps.core.utils import normalize_part_no

EMBEDDING_DIM = 1024


class Category(models.Model):
    name = models.CharField("名称", max_length=100)
    name_en = models.CharField("英文名", max_length=100)
    parent = models.ForeignKey("self", verbose_name="上级", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    margin_rate = models.DecimalField("毛利率", max_digits=4, decimal_places=2, default=0.30)

    class Meta:
        verbose_name = verbose_name_plural = "品类"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    OEM, AFTERMARKET = "oem", "aftermarket"
    TYPE_CHOICES = [(OEM, "主机厂 OEM"), (AFTERMARKET, "副厂 Aftermarket")]

    name = models.CharField("品牌", max_length=100, unique=True)
    type = models.CharField("类型", max_length=20, choices=TYPE_CHOICES)

    class Meta:
        verbose_name = verbose_name_plural = "品牌"
        ordering = ["type", "name"]

    def __str__(self):
        return self.name


class VehicleModel(models.Model):
    make = models.CharField("品牌", max_length=50)
    series = models.CharField("系列", max_length=50)
    year_from = models.PositiveSmallIntegerField("起始年份", null=True, blank=True)
    year_to = models.PositiveSmallIntegerField("截止年份", null=True, blank=True)
    engine = models.CharField("发动机", max_length=50, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "车型"
        ordering = ["make", "series"]

    def __str__(self):
        years = f" ({self.year_from or ''}-{self.year_to or ''})" if self.year_from or self.year_to else ""
        return f"{self.make} {self.series}{years}"


class Product(TimeStampedModel):
    DRAFT, ACTIVE, ARCHIVED = "draft", "active", "archived"
    STATUS_CHOICES = [(DRAFT, "草稿"), (ACTIVE, "在售"), (ARCHIVED, "已归档")]

    sku = models.CharField("SKU", max_length=30, unique=True)
    name_en = models.CharField("英文名", max_length=200, blank=True)
    name_cn = models.CharField("中文名", max_length=200, blank=True)
    category = models.ForeignKey(Category, verbose_name="品类", on_delete=models.PROTECT, related_name="products")
    specs = models.JSONField("规格", default=dict, blank=True)
    weight_kg = models.DecimalField("重量(kg)", max_digits=8, decimal_places=3, null=True, blank=True)
    package_l_cm = models.DecimalField("包装长(cm)", max_digits=7, decimal_places=1, null=True, blank=True)
    package_w_cm = models.DecimalField("包装宽(cm)", max_digits=7, decimal_places=1, null=True, blank=True)
    package_h_cm = models.DecimalField("包装高(cm)", max_digits=7, decimal_places=1, null=True, blank=True)
    qty_per_package = models.PositiveIntegerField("每包数量", null=True, blank=True)
    description_en = models.TextField("英文描述", blank=True)
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    merged_into = models.ForeignKey("self", verbose_name="合并至", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from")
    completeness_score = models.PositiveSmallIntegerField("完整度", default=0)
    embedding = VectorField(dimensions=EMBEDDING_DIM, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = verbose_name_plural = "产品"
        ordering = ["sku"]
        indexes = [
            HnswIndex(name="product_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64, opclasses=["vector_cosine_ops"]),
        ]

    def __str__(self):
        return f"{self.sku} {self.name_en or self.name_cn}"

    @property
    def primary_image(self):
        images = list(self.images.all())
        return next((i for i in images if i.is_primary), images[0] if images else None)

    def numbers_of(self, type_):
        return [pn for pn in self.part_numbers.all() if pn.type == type_]

    @property
    def oe_numbers(self):
        return self.numbers_of(PartNumber.OE)

    @property
    def cross_numbers(self):
        return self.numbers_of(PartNumber.CROSS)

    def embedding_text(self) -> str:
        parts = [self.name_en, self.name_cn, self.category.name_en, self.category.name]
        parts += [f"{k} {v}" for k, v in (self.specs or {}).items()]
        parts += [str(f.vehicle_model) for f in self.fitments.all()]
        parts += [f"{pn.brand.name if pn.brand else ''} {pn.number}".strip() for pn in self.part_numbers.all()]
        return " | ".join(p for p in parts if p)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("图片", upload_to="products/")
    is_primary = models.BooleanField("主图", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "产品图片"


class PartNumber(models.Model):
    OE, CROSS, SUPPLIER = "oe", "cross", "supplier"
    TYPE_CHOICES = [(OE, "OE 原厂号"), (CROSS, "Cross 参考号"), (SUPPLIER, "供应商料号")]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="part_numbers")
    number = models.CharField("号码(原始)", max_length=60)
    normalized = models.CharField("号码(归一化)", max_length=60, db_index=True, editable=False)
    type = models.CharField("类型", max_length=10, choices=TYPE_CHOICES)
    brand = models.ForeignKey(Brand, verbose_name="品牌", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = verbose_name_plural = "零件号"
        ordering = ["type", "normalized"]
        constraints = [
            models.UniqueConstraint(fields=["product", "normalized", "brand"], name="uniq_product_number_brand"),
        ]
        indexes = [
            GinIndex(fields=["normalized"], opclasses=["gin_trgm_ops"], name="partnumber_trgm"),
        ]

    def __str__(self):
        return f"{self.brand or ''} {self.number}".strip()

    def save(self, *args, **kwargs):
        self.normalized = normalize_part_no(self.number)
        super().save(*args, **kwargs)


class Fitment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="fitments")
    vehicle_model = models.ForeignKey(VehicleModel, verbose_name="车型", on_delete=models.CASCADE, related_name="fitments")
    note = models.CharField("备注", max_length=200, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "适配车型"
        constraints = [models.UniqueConstraint(fields=["product", "vehicle_model"], name="uniq_fitment")]

from django.db import models

from apps.core.models import TimeStampedModel


class Supplier(TimeStampedModel):
    name = models.CharField("供应商", max_length=100, unique=True)
    region = models.CharField("地区", max_length=50, blank=True)
    contact = models.CharField("联系人/方式", max_length=200, blank=True)
    product_lines = models.CharField("主营产品线", max_length=300, blank=True)
    rating = models.PositiveSmallIntegerField("评级(1-5)", default=3)
    quality_notes = models.TextField("质量记录", blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "供应商"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierOffer(TimeStampedModel):
    CURRENCY_CHOICES = [("CNY", "CNY"), ("USD", "USD"), ("EUR", "EUR")]

    supplier = models.ForeignKey(Supplier, verbose_name="供应商", on_delete=models.CASCADE, related_name="offers")
    product = models.ForeignKey("catalog.Product", verbose_name="产品", null=True, blank=True, on_delete=models.CASCADE, related_name="offers")
    supplier_part_no = models.CharField("供应商料号", max_length=60, blank=True)
    cost_price = models.DecimalField("成本价", max_digits=12, decimal_places=2)
    currency = models.CharField("币种", max_length=3, choices=CURRENCY_CHOICES, default="CNY")
    moq = models.PositiveIntegerField("MOQ", null=True, blank=True)
    lead_time_days = models.PositiveIntegerField("交期(天)", null=True, blank=True)
    packaging = models.CharField("包装", max_length=200, blank=True)
    quoted_at = models.DateField("报价日期")
    source_import_row = models.ForeignKey("ingest.ImportRow", verbose_name="来源导入行", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = verbose_name_plural = "供应商报价"
        ordering = ["-quoted_at"]

    def __str__(self):
        return f"{self.supplier} {self.supplier_part_no} {self.cost_price}{self.currency}"

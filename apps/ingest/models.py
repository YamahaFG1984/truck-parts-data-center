from django.db import models

from apps.core.models import TimeStampedModel


class ImportBatch(TimeStampedModel):
    UPLOADED, PARSING, REVIEWING, DONE, FAILED = "uploaded", "parsing", "reviewing", "done", "failed"
    STATUS_CHOICES = [(UPLOADED, "已上传"), (PARSING, "解析中"), (REVIEWING, "待审核"), (DONE, "已完成"), (FAILED, "失败")]

    supplier = models.ForeignKey("suppliers.Supplier", verbose_name="供应商", on_delete=models.CASCADE, related_name="import_batches")
    file = models.FileField("文件", upload_to="imports/")
    file_type = models.CharField("类型", max_length=10)
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default=UPLOADED)
    column_mapping = models.JSONField("列映射", default=dict, blank=True)
    stats = models.JSONField("统计", default=dict, blank=True)
    log = models.TextField("日志", blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "导入批次"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.supplier} {self.file.name.rsplit('/', 1)[-1]}"

    def add_log(self, message):
        self.log = f"{self.log}{message}\n"


class ImportRow(models.Model):
    PENDING, APPROVED, REJECTED, NEW_PRODUCT = "pending", "approved", "rejected", "new_product"
    STATUS_CHOICES = [(PENDING, "待审核"), (APPROVED, "已通过"), (REJECTED, "已驳回"), (NEW_PRODUCT, "已新建SKU")]

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_index = models.PositiveIntegerField("行号")
    raw = models.JSONField("原始数据", default=dict)
    extracted = models.JSONField("抽取结果", default=dict)
    errors = models.JSONField("校验问题", default=list)
    matched_product = models.ForeignKey("catalog.Product", verbose_name="匹配产品", null=True, blank=True, on_delete=models.SET_NULL)
    match_method = models.CharField("匹配方式", max_length=20, blank=True)
    confidence = models.PositiveSmallIntegerField("置信度", default=0)
    preselected = models.BooleanField("预选通过", default=False)
    status = models.CharField("状态", max_length=12, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        verbose_name = verbose_name_plural = "导入行"
        ordering = ["batch", "row_index"]

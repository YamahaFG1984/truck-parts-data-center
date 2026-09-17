from django.db import models


class DataIssue(models.Model):
    SEVERITY_CHOICES = [("high", "高"), ("medium", "中"), ("low", "低")]
    CATEGORY_CHOICES = [("missing", "缺失"), ("duplicate", "重复"), ("format", "格式"), ("consistency", "一致性")]

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="issues")
    rule_code = models.CharField("规则", max_length=40, db_index=True)
    category = models.CharField("类别", max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField("严重度", max_length=10, choices=SEVERITY_CHOICES)
    field = models.CharField("字段", max_length=50, blank=True)
    message = models.CharField("说明", max_length=300)
    related_product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    resolved = models.BooleanField("已解决", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "数据问题"
        ordering = ["resolved", "rule_code"]

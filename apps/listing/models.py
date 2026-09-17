from django.db import models

from apps.core.models import TimeStampedModel


class ListingContent(TimeStampedModel):
    PLATFORM_CHOICES = [("alibaba", "Alibaba"), ("shopify", "Shopify")]
    STATUS_CHOICES = [("draft", "草稿"), ("confirmed", "已确认")]

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="listings")
    platform = models.CharField("平台", max_length=10, choices=PLATFORM_CHOICES)
    title = models.CharField("标题", max_length=300)
    keywords = models.JSONField("关键词", default=list)
    bullets = models.JSONField("卖点", default=list)
    description = models.TextField("描述", blank=True)
    faq = models.JSONField("FAQ", default=list)
    warnings = models.JSONField("校验提示", default=list)
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="draft")

    class Meta:
        verbose_name = verbose_name_plural = "上架文案"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.product.sku} {self.platform}"

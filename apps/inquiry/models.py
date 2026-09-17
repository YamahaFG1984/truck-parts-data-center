from django.db import models

from apps.core.models import TimeStampedModel


class Inquiry(TimeStampedModel):
    CHANNEL_CHOICES = [("email", "邮件"), ("whatsapp", "WhatsApp"), ("alibaba", "Alibaba"), ("other", "其他")]

    customer = models.CharField("客户", max_length=100, blank=True)
    channel = models.CharField("渠道", max_length=20, choices=CHANNEL_CHOICES, default="email")
    raw_text = models.TextField("询价原文", blank=True)
    image = models.ImageField("图片", upload_to="inquiries/", blank=True)
    image_result = models.JSONField("图片识别结果", null=True, blank=True)
    quote_email = models.TextField("报价邮件", blank=True)
    elapsed_ms = models.PositiveIntegerField("处理耗时(ms)", default=0)

    class Meta:
        verbose_name = verbose_name_plural = "询价"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.customer or '客户'} {self.created_at:%Y-%m-%d}"


class InquiryLine(models.Model):
    FEEDBACK_CHOICES = [("correct", "正确"), ("wrong", "错误")]

    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveSmallIntegerField(default=0)
    query = models.CharField("询价行", max_length=500)
    parsed = models.JSONField("解析结果", default=dict)
    candidates = models.JSONField("候选快照", default=list)
    selected_product = models.ForeignKey("catalog.Product", verbose_name="选中产品", null=True, blank=True, on_delete=models.SET_NULL)
    qty = models.PositiveIntegerField("数量", default=1)
    unit_price_usd = models.DecimalField("单价(USD)", max_digits=12, decimal_places=2, null=True, blank=True)
    feedback = models.CharField("反馈", max_length=10, choices=FEEDBACK_CHOICES, blank=True)
    feedback_note = models.CharField("反馈备注", max_length=300, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "询价行"
        ordering = ["inquiry", "position"]

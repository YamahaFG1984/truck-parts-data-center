from django.db import models


class PromptTemplate(models.Model):
    code = models.CharField("代码", max_length=50)
    version = models.PositiveIntegerField("版本", default=1)
    content = models.TextField("内容")
    is_active = models.BooleanField("启用", default=True)
    note = models.CharField("说明", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "提示词模板"
        ordering = ["code", "-version"]
        constraints = [models.UniqueConstraint(fields=["code", "version"], name="uniq_prompt_version")]

    def __str__(self):
        return f"{self.code} v{self.version}"


class AICallLog(models.Model):
    task = models.CharField("任务", max_length=50)
    model = models.CharField("模型", max_length=100)
    prompt_code = models.CharField("提示词", max_length=50, blank=True)
    prompt_version = models.PositiveIntegerField("提示词版本", null=True, blank=True)
    request = models.JSONField("请求", default=dict)
    response = models.TextField("响应", blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField("耗时(ms)", default=0)
    success = models.BooleanField("成功", default=True)
    error = models.TextField("错误", blank=True)
    is_mock = models.BooleanField("Mock", default=False)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "AI 调用日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.task} {self.model} {self.latency_ms}ms"

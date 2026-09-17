from django.contrib import admin

from .models import DataIssue


@admin.register(DataIssue)
class DataIssueAdmin(admin.ModelAdmin):
    list_display = ["product", "rule_code", "severity", "message", "resolved"]
    list_filter = ["rule_code", "severity", "resolved"]
    raw_id_fields = ["product", "related_product"]

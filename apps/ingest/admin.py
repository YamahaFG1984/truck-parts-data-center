from django.contrib import admin

from .models import ImportBatch, ImportRow


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ["id", "supplier", "file", "status", "created_at"]
    list_filter = ["status", "supplier"]


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ["batch", "row_index", "matched_product", "match_method", "confidence", "status"]
    list_filter = ["status", "match_method"]
    raw_id_fields = ["matched_product", "batch"]

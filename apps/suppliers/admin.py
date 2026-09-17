from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Supplier, SupplierOffer


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "product_lines", "rating"]
    search_fields = ["name"]


@admin.register(SupplierOffer)
class SupplierOfferAdmin(ImportExportModelAdmin):
    list_display = ["supplier", "product", "supplier_part_no", "cost_price", "currency", "moq", "lead_time_days", "quoted_at"]
    list_filter = ["supplier", "currency"]
    search_fields = ["supplier_part_no", "product__sku"]
    raw_id_fields = ["product", "source_import_row"]

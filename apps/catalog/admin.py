from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Brand, Category, Fitment, PartNumber, Product, ProductImage, VehicleModel


class PartNumberInline(admin.TabularInline):
    model = PartNumber
    extra = 1
    autocomplete_fields = ["brand"]
    readonly_fields = ["normalized"]


class FitmentInline(admin.TabularInline):
    model = Fitment
    extra = 1
    autocomplete_fields = ["vehicle_model"]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = ["sku", "name_en", "name_cn", "category", "status", "completeness_score", "updated_at"]
    list_filter = ["status", "category"]
    search_fields = ["sku", "name_en", "name_cn", "part_numbers__normalized"]
    inlines = [PartNumberInline, FitmentInline, ProductImageInline]
    readonly_fields = ["completeness_score", "merged_into"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "name_en", "parent", "margin_rate"]
    list_editable = ["margin_rate"]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "type"]
    list_filter = ["type"]
    search_fields = ["name"]


@admin.register(VehicleModel)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ["make", "series", "year_from", "year_to", "engine"]
    list_filter = ["make"]
    search_fields = ["make", "series"]


@admin.register(PartNumber)
class PartNumberAdmin(ImportExportModelAdmin):
    list_display = ["number", "normalized", "type", "brand", "product"]
    list_filter = ["type", "brand"]
    search_fields = ["normalized", "number", "product__sku"]
    autocomplete_fields = ["brand"]
    raw_id_fields = ["product"]

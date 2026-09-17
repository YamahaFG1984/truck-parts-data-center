from django.contrib import admin

from .models import ListingContent


@admin.register(ListingContent)
class ListingContentAdmin(admin.ModelAdmin):
    list_display = ["product", "platform", "title", "status", "updated_at"]
    list_filter = ["platform", "status"]
    raw_id_fields = ["product"]

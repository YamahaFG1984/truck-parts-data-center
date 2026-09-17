from django.contrib import admin

from .models import Inquiry, InquiryLine


class InquiryLineInline(admin.TabularInline):
    model = InquiryLine
    extra = 0
    fields = ["position", "query", "selected_product", "qty", "unit_price_usd", "feedback", "feedback_note"]
    raw_id_fields = ["selected_product"]


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "channel", "elapsed_ms", "created_at"]
    inlines = [InquiryLineInline]


@admin.register(InquiryLine)
class InquiryLineAdmin(admin.ModelAdmin):
    list_display = ["inquiry", "query", "selected_product", "feedback", "feedback_note"]
    list_filter = ["feedback"]
    raw_id_fields = ["selected_product", "inquiry"]

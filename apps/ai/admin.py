from django.contrib import admin

from .models import AICallLog, PromptTemplate


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ["code", "version", "is_active", "note", "created_at"]
    list_filter = ["code", "is_active"]
    save_as = True  # "另存为新对象" = create a new version from the current one


@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "task", "model", "prompt_code", "prompt_version", "latency_ms", "tokens_in", "tokens_out", "success", "is_mock"]
    list_filter = ["task", "success", "is_mock", "model"]
    readonly_fields = [f.name for f in AICallLog._meta.fields]

    def has_add_permission(self, request):
        return False

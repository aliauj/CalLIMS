from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'object_repr', 'ip_address')
    list_filter = ('action', 'model_name')
    search_fields = ('user__email', 'object_repr', 'model_name')
    readonly_fields = ('timestamp', 'user', 'action', 'app_label', 'model_name', 'object_id', 'object_repr', 'old_values', 'new_values', 'ip_address', 'user_agent')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

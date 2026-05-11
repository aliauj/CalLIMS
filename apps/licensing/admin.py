from django.contrib import admin
from .models import LabSettings, LicenseRecord


@admin.register(LabSettings)
class LabSettingsAdmin(admin.ModelAdmin):
    list_display = ('lab_name', 'lab_subtitle', 'email', 'updated_at')
    fieldsets = (
        ('Branding', {'fields': ('lab_name', 'lab_subtitle', 'logo')}),
        ('Contact', {'fields': ('address', 'phone', 'email', 'website')}),
        ('Accreditation', {'fields': ('accreditation_body', 'accreditation_number')}),
        ('Documents', {'fields': ('footer_text',)}),
    )


@admin.register(LicenseRecord)
class LicenseRecordAdmin(admin.ModelAdmin):
    list_display = ('license_id', 'issued_to', 'tier', 'valid_until', 'is_active', 'activated_at')
    list_filter = ('tier', 'is_active')
    search_fields = ('license_id', 'issued_to', 'issued_to_email')
    readonly_fields = ('license_key', 'activated_at', 'activated_by')
    fieldsets = (
        ('License', {'fields': ('license_id', 'license_key', 'is_active')}),
        ('Customer', {'fields': ('issued_to', 'issued_to_email')}),
        ('Subscription', {'fields': ('tier', 'max_users', 'valid_from', 'valid_until', 'modules_json')}),
        ('Meta', {'fields': ('activated_at', 'activated_by', 'notes')}),
    )

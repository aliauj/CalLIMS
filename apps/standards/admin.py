from django.contrib import admin
from .models import ReferenceStandard, MeasurementUnit


@admin.register(MeasurementUnit)
class MeasurementUnitAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'quantity_type')
    search_fields = ('symbol', 'name')


@admin.register(ReferenceStandard)
class ReferenceStandardAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'name', 'status', 'uncertainty_value', 'uncertainty_unit', 'calibration_due_date', 'is_valid')
    list_filter = ('status',)
    search_fields = ('serial_number', 'name', 'certificate_number')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'calibration_due_date'

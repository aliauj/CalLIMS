from django.contrib import admin
from .models import CalibrationJob, CalibrationMethod, MeasurementResult


class MeasurementResultInline(admin.TabularInline):
    model = MeasurementResult
    extra = 0
    fields = ('parameter', 'measured_value', 'unit', 'standard_uncertainty', 'coverage_factor_k', 'expanded_uncertainty', 'pass_fail')


@admin.register(CalibrationMethod)
class CalibrationMethodAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'version', 'coverage_factor', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(CalibrationJob)
class CalibrationJobAdmin(admin.ModelAdmin):
    list_display = ('job_number', 'instrument', 'status', 'assigned_to', 'priority', 'received_date', 'due_date')
    list_filter = ('status', 'priority', 'assigned_to')
    search_fields = ('job_number', 'instrument__asset_tag', 'instrument__serial_number')
    readonly_fields = ('created_at', 'updated_at', 'status')
    inlines = [MeasurementResultInline]
    date_hierarchy = 'received_date'

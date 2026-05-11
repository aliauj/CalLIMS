from django.contrib import admin
from .models import Instrument, InstrumentCategory


@admin.register(InstrumentCategory)
class InstrumentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'description', 'serial_number', 'status', 'client', 'next_calibration_date', 'is_overdue')
    list_filter = ('status', 'category', 'client')
    search_fields = ('asset_tag', 'serial_number', 'description')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'next_calibration_date'
    list_select_related = ('client', 'category')

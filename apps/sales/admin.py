from django.contrib import admin
from .models import RFQ, RFQItem


class RFQItemInline(admin.TabularInline):
    model = RFQItem
    extra = 0
    fields = ('sequence', 'description', 'manufacturer', 'model_number', 'serial_number', 'quantity', 'registered_instrument')


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = ('rfq_number', 'client', 'status', 'priority', 'received_date', 'created_by', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('rfq_number', 'client__name', 'contact_person')
    autocomplete_fields = ('client', 'created_by', 'reviewed_by')
    readonly_fields = ('rfq_number', 'created_at', 'updated_at')
    inlines = [RFQItemInline]
    fieldsets = (
        (None, {'fields': ('rfq_number', 'client', 'status', 'priority')}),
        ('Schedule', {'fields': ('received_date', 'required_by')}),
        ('Contact', {'fields': ('contact_person', 'contact_email', 'contact_phone')}),
        ('Scope', {'fields': ('scope_description', 'notes')}),
        ('Workflow', {'fields': ('created_by', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'sent_to_lab_at')}),
        ('Instruments', {'fields': ('instruments',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

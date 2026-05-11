from django.contrib import admin
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_number', 'job', 'status', 'issue_date', 'signed_by', 'signed_at')
    list_filter = ('status',)
    search_fields = ('certificate_number', 'job__job_number')
    readonly_fields = ('created_at', 'updated_at', 'content_hash', 'signed_at')

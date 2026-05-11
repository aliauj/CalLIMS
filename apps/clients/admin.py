from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'client_type', 'contact_person', 'email', 'is_active')
    list_filter = ('client_type', 'is_active')
    search_fields = ('name', 'email', 'contact_person')

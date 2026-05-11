from django.urls import path
from . import views

app_name = 'licensing'

urlpatterns = [
    path('expired/', views.license_expired, name='expired'),
    path('status/', views.license_status, name='status'),
    path('activate/', views.activate_license, name='activate'),
    path('settings/', views.lab_settings_edit, name='lab_settings'),
]

from django.urls import path
from . import views

app_name = 'compliance'

urlpatterns = [
    path('audit-log/', views.audit_log_list, name='audit_log'),
]

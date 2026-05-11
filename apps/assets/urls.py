from django.urls import path
from . import views

app_name = 'instruments'

urlpatterns = [
    path('', views.instrument_list, name='instrument_list'),
    path('register/', views.instrument_create, name='instrument_create'),
    path('<int:pk>/', views.instrument_detail, name='instrument_detail'),
    path('bulk-delete/', views.instrument_bulk_delete, name='instrument_bulk_delete'),
    path('export/excel/', views.instrument_export_excel, name='instrument_export_excel'),
    path('export/pdf/', views.instrument_export_pdf, name='instrument_export_pdf'),
    path('<int:pk>/edit/', views.instrument_edit, name='instrument_edit'),
    path('<int:pk>/duplicate/', views.instrument_duplicate, name='instrument_duplicate'),
    path('<int:pk>/sticker/', views.sticker_pdf, name='sticker_pdf'),
]

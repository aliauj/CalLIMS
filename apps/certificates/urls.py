from django.urls import path
from . import views

app_name = 'certificates'

urlpatterns = [
    path('', views.certificate_list, name='certificate_list'),
    path('<int:pk>/', views.certificate_detail, name='certificate_detail'),
    path('<int:pk>/edit/', views.certificate_edit, name='certificate_edit'),
    path('<int:pk>/sign/', views.certificate_sign, name='certificate_sign'),
    path('<int:pk>/issue/', views.certificate_issue, name='certificate_issue'),
    path('<int:pk>/revoke/', views.certificate_revoke, name='certificate_revoke'),
    path('<int:pk>/regenerate-pdf/', views.certificate_regenerate_pdf, name='certificate_regenerate_pdf'),
    path('<int:pk>/pdf/', views.certificate_pdf, name='certificate_pdf'),
    path('<int:pk>/print/', views.certificate_print, name='certificate_print'),
    path('<int:pk>/verify/', views.certificate_verify, name='certificate_verify'),
    path('<int:pk>/sticker/', views.certificate_sticker_pdf, name='certificate_sticker_pdf'),
]

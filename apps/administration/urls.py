from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/toggle/', views.user_toggle_active, name='user_toggle'),
    path('users/<int:pk>/permissions/', views.user_permissions_save, name='user_permissions_save'),
    path('users/<int:pk>/change-role/', views.user_change_role, name='user_change_role'),

    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<int:pk>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:pk>/delete/', views.role_delete, name='role_delete'),

    path('authorizations/', views.authorization_matrix, name='authorization_matrix'),
    path('authorizations/create/', views.authorization_create, name='authorization_create'),
    path('authorizations/<int:pk>/edit/', views.authorization_edit, name='authorization_edit'),

    path('methods/', views.method_list, name='method_list'),
    path('methods/create/', views.method_create, name='method_create'),
    path('methods/<int:pk>/edit/', views.method_edit, name='method_edit'),
    path('methods/<int:method_pk>/points/', views.method_points, name='method_points'),
    path('methods/<int:method_pk>/points/add/', views.point_create, name='point_create'),
    path('points/<int:pk>/edit/', views.point_edit, name='point_edit'),
    path('points/<int:pk>/delete/', views.point_delete, name='point_delete'),

    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),

    path('units/', views.unit_list, name='unit_list'),
    path('units/create/', views.unit_create, name='unit_create'),
    path('units/<int:pk>/edit/', views.unit_edit, name='unit_edit'),

    path('certificate-templates/', views.certificate_template_list, name='certificate_template_list'),
    path('certificate-templates/create/', views.certificate_template_create, name='certificate_template_create'),
    path('certificate-templates/<int:pk>/edit/', views.certificate_template_edit, name='certificate_template_edit'),
    path('certificate-templates/<int:pk>/delete/', views.certificate_template_delete, name='certificate_template_delete'),

    path('reports/', views.report_overview, name='report_overview'),
    path('reports/export/jobs/', views.report_jobs_export, name='report_jobs_export'),
    path('reports/export/instruments/', views.report_instruments_export, name='report_instruments_export'),
]

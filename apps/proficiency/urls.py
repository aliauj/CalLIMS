from django.urls import path

from . import views

app_name = 'proficiency'

urlpatterns = [
    path('', views.scheme_list, name='scheme_list'),
    path('create/', views.scheme_create, name='scheme_create'),
    path('<int:pk>/', views.scheme_detail, name='scheme_detail'),
    path('<int:pk>/edit/', views.scheme_edit, name='scheme_edit'),
    path('<int:scheme_pk>/participate/', views.participation_create, name='participation_create'),
    path('participation/<int:pk>/', views.participation_detail, name='participation_detail'),
    path('participation/<int:pk>/submit/', views.submit_results, name='submit_results'),
    path('participation/<int:pk>/corrective/', views.corrective_action, name='corrective_action'),
    path('providers/', views.provider_list, name='provider_list'),
    path('providers/create/', views.provider_create, name='provider_create'),
    path('providers/<int:pk>/edit/', views.provider_edit, name='provider_edit'),
]

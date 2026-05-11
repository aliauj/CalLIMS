from django.urls import path
from . import views

app_name = 'nonconformance'

urlpatterns = [
    path('', views.nc_list, name='nc_list'),
    path('raise/', views.nc_create, name='nc_create'),
    path('<int:pk>/', views.nc_detail, name='nc_detail'),
    path('<int:pk>/edit/', views.nc_edit, name='nc_edit'),
    path('<int:pk>/close/', views.nc_close, name='nc_close'),
    path('<int:nc_pk>/actions/add/', views.capa_create, name='capa_create'),
    path('actions/<int:pk>/edit/', views.capa_edit, name='capa_edit'),
    path('actions/<int:pk>/complete/', views.capa_complete, name='capa_complete'),
    path('actions/<int:pk>/verify/', views.capa_verify, name='capa_verify'),
]

from django.urls import path
from . import views

app_name = 'standards'

urlpatterns = [
    path('', views.standard_list, name='standard_list'),
    path('create/', views.standard_create, name='standard_create'),
    path('<int:pk>/', views.standard_detail, name='standard_detail'),
    path('<int:pk>/edit/', views.standard_edit, name='standard_edit'),
]

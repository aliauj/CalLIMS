from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.rfq_list, name='rfq_list'),
    path('create/', views.rfq_create, name='rfq_create'),
    path('<int:pk>/', views.rfq_detail, name='rfq_detail'),
    path('<int:pk>/items/add/', views.rfq_add_item, name='rfq_add_item'),
    path('<int:pk>/items/<int:item_pk>/delete/', views.rfq_delete_item, name='rfq_delete_item'),
    path('<int:pk>/accept/', views.rfq_accept, name='rfq_accept'),
    path('<int:pk>/reject/', views.rfq_reject, name='rfq_reject'),
    path('<int:pk>/instruments/link/', views.rfq_link_instrument, name='rfq_link_instrument'),
    path('<int:pk>/instruments/unlink/<int:instrument_pk>/', views.rfq_unlink_instrument, name='rfq_unlink_instrument'),
    path('<int:pk>/instruments/create/', views.rfq_create_instrument, name='rfq_create_instrument'),
    path('<int:pk>/send-to-lab/', views.rfq_send_to_lab, name='rfq_send_to_lab'),
    path('<int:pk>/delete/', views.rfq_delete, name='rfq_delete'),
]

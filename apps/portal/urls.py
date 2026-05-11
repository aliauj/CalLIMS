from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.portal_dashboard, name='dashboard'),
    path('instruments/<int:pk>/', views.portal_instrument_detail, name='instrument_detail'),
]

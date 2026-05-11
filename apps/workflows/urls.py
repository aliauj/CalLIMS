from django.urls import path
from . import views

app_name = 'workflows'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/create/', views.job_create, name='job_create'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
    path('jobs/<int:pk>/results/', views.job_enter_results, name='job_enter_results'),
    path('jobs/<int:pk>/assign/', views.job_assign, name='job_assign'),
    path('jobs/<int:pk>/start/', views.job_start, name='job_start'),
    path('jobs/<int:pk>/submit-review/', views.job_submit_review, name='job_submit_review'),
    path('jobs/<int:pk>/approve/', views.job_approve, name='job_approve'),
    path('jobs/<int:pk>/reject/', views.job_reject, name='job_reject'),
    path('jobs/<int:pk>/complete/', views.job_complete, name='job_complete'),
    path('jobs/<int:pk>/hold/', views.job_hold, name='job_hold'),
    path('jobs/<int:pk>/delete/', views.job_delete, name='job_delete'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('resume/', views.resume, name='resume'),
    path('ai_analysis/', views.ai_analysis, name='ai_analysis'),
    path('clear_session/', views.clear_session, name='clear_session'),
]

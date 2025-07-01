from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("resume/", views.resume, name="resume"),
    path("ai_analysis/", views.ai_analysis, name="ai_analysis"),
    path("clear_session/", views.clear_session, name="clear_session"),
    path("ats_resume/", views.ats_resume, name="ats_resume"),
    path("api/get-ai-analysis/", views.api_get_ai_analysis, name="api_get_ai_analysis"),
    path(
        "api/get-job-listings/", views.api_get_job_listings, name="api_get_job_listings"
    ),
]

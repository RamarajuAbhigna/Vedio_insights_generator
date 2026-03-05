from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('upload/', views.upload_video, name='upload_video'),
    path('library/', views.video_list, name='video_list'),
    path('delete/<int:pk>/', views.delete_video, name='delete_video'),
    path('video/<int:video_id>/download-report/', views.download_pdf_report, name='download_pdf_report'),
]
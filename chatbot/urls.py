from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.ai_chatbot_view, name='ai_chatbot'),
    path('chat/<int:video_id>/', views.ai_chatbot_view, name='ai_chatbot_with_video'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('history/', views.chat_history_view, name='chat_history'),
    path('history/<int:video_id>/', views.chat_history_view, name='chat_history_video'),
]
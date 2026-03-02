from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.ai_chatbot_view, name='ai_chatbot'),
    path('api/chat/', views.chat_api, name='chat_api'),
]
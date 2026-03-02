from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view

urlpatterns = [
    # System Administration
    path('admin/', admin.site.urls),
    
    # Public Landing Page
    path('', landing_view, name='landing'),
    
    # User & Admin Account Management (Auth, Signup, SMTP)
    path('accounts/', include('accounts.urls')),

    # Video Ingestion (Upload & YouTube Link handling)
    path('portal/', include('videos.urls')),

    # AI Pipeline & Insights (Vision, NLP, Wavy Charts)
    path('analysis/', include('analysis.urls')),

    # AI Interaction (Natural Language Q&A Chatbot)
    path('neural-chat/', include('chatbot.urls')),
]

# ---------------- MEDIA SERVING CONFIGURATION ----------------
# Enables Django to serve large video files (up to 90MB) from the 
# /media/ directory during local development .
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
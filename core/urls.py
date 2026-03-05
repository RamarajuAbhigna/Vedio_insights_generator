from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from core.views import landing_view

urlpatterns = [
    # System Administration
    path('admin/', admin.site.urls),

    # Public Landing Page
    path('', landing_view, name='landing'),

    # User & Admin Account Management (Auth, Signup, SMTP)
    path('accounts/', include('accounts.urls')),

    # ✅ Password Reset URLs — HTML email fix
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        html_email_template_name='registration/password_reset_email.html',  # ← KEY FIX
        email_template_name='registration/password_reset_email.html',
    ), name='password_reset'),

    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    # Video Ingestion (Upload & YouTube Link handling)
    path('portal/', include('videos.urls')),

    # AI Pipeline & Insights (Vision, NLP, Wavy Charts)
    path('analysis/', include('analysis.urls')),

    # AI Interaction (Natural Language Q&A Chatbot)
    path('neural-chat/', include('chatbot.urls')),
]

# ---------------- MEDIA SERVING CONFIGURATION ----------------
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
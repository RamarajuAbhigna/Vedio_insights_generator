from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import (
    login_view, logout_view, signup_view,
    verify_otp_view, profile_view, custom_password_reset
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    path('verify-otp/', verify_otp_view, name='verify_otp'),
    path('profile/', profile_view, name='profile'),

    # ✅ MUST be before include('django.contrib.auth.urls')
    path('password_reset/', custom_password_reset, name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    # ⬇️ This must come AFTER your custom paths
    path('', include('django.contrib.auth.urls')),
]
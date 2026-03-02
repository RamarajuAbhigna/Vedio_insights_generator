from django.urls import path
from . import views

urlpatterns = [
    # --- USER ROUTES ---
    path('insights/<int:pk>/', views.video_insight_detail, name='video_insight_detail'),
    path('hub/', views.analytics_dashboard, name='analytics_dashboard'), 
    
    # --- ADMIN GOVERNANCE ROUTES ---
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_user_management, name='admin_user_management'),
    path('admin/analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin/monitor/', views.admin_ai_monitor, name='admin_ai_monitor'),
    
    # --- NEW: USER MANAGEMENT ACTIONS ---
    # These match the forms in your admin_user_management.html
    path('admin/users/toggle/<int:user_id>/', views.admin_toggle_status, name='admin_toggle_status'),
    path('admin/users/delete/<int:user_id>/', views.admin_delete_user, name='admin_delete_user'),
]
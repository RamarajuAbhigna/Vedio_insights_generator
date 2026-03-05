from django.db import models
from django.conf import settings

class VideoAnalysis(models.Model):
    # Link to Custom User Model
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    
    # Ingestion Nodes
    video_file = models.FileField(upload_to='videos/', null=True, blank=True)
    youtube_url = models.URLField(null=True, blank=True)
    
    # AI Output Fields (Gemini)
    transcript = models.TextField(null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    keywords = models.JSONField(default=list)
    
    # Analysis Metrics
    engagement_data = models.JSONField(default=list, null=True, blank=True)
    objects_detected = models.JSONField(default=list)
    key_moments = models.JSONField(default=list, blank=True)
    activity_type = models.CharField(max_length=100, default="General Analysis")

    # ── NEW: ML Model Results (Features 6, 7, 8, 11) ──────────────
    # Feature 6 — YOLOv8 Human Presence Detection
    human_presence_data = models.JSONField(default=dict, null=True, blank=True)
    # Feature 7 — OpenCV Haar Cascade Face Detection
    face_detection_data = models.JSONField(default=dict, null=True, blank=True)
    # Feature 8 — YOLOv8 Activity Recognition (full distribution data)
    activity_ml_data = models.JSONField(default=dict, null=True, blank=True)
    # Tracks if local ML models have already run (avoid re-running)
    ml_processed = models.BooleanField(default=False)
    # ──────────────────────────────────────────────────────────────

    created_at = models.DateTimeField(auto_now_add=True)
    ai_processed = models.BooleanField(default=False)
    ai_failed = models.BooleanField(default=False)


class ChatMessage(models.Model):
    video = models.ForeignKey(VideoAnalysis, on_delete=models.CASCADE, related_name='chat_messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_message = models.TextField()
    ai_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.video.title} | {self.user.email}"
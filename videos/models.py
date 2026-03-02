from django.db import models
from django.conf import settings

class VideoAnalysis(models.Model):
    # Link to Custom User Model
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    
    # Ingestion Nodes
    video_file = models.FileField(upload_to='videos/', null=True, blank=True) # Binary Node
    youtube_url = models.URLField(null=True, blank=True) # Stream Node
    
    # AI Output Fields (Synchronized with Pipeline)
    transcript = models.TextField(null=True, blank=True) # Speech-to-Text Node
    summary = models.TextField(null=True, blank=True)
    keywords = models.JSONField(default=list) # NLP Topic Node
    
    # Analysis Metrics (Used for Wavy Charts & Vision Tags)
    # Changed default to list to match the bar chart iteration in templates
    engagement_data = models.JSONField(default=list, null=True, blank=True) 
    objects_detected = models.JSONField(default=list) # Computer Vision Node
    
    # NEW: Added for Feature 12 (Activity Recognition)
    activity_type = models.CharField(max_length=100, default="General Analysis")
    
    created_at = models.DateTimeField(auto_now_add=True)
    ai_processed = models.BooleanField(default=False)
    ai_failed = models.BooleanField(default=False)

    def __str__(self):
        # FIXED: Using email because username is None in your custom model
        return f"{self.title} | {self.user.email}"
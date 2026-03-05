from django.db import models
from django.conf import settings
from videos.models import VideoAnalysis

class ChatMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    video = models.ForeignKey(
        VideoAnalysis,
        on_delete=models.CASCADE,
        related_name='video_chat_messages'
    )
    user_message = models.TextField()
    ai_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.email} | {self.video.title} | {self.created_at}"
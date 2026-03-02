import yt_dlp
import os
from django.conf import settings
import uuid

def download_youtube_video(url):
    output_dir = os.path.join(settings.MEDIA_ROOT, "videos")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"yt_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(output_dir, filename)

    ydl_opts = {
        'format': 'mp4/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return f"videos/{filename}"

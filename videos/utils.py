import yt_dlp
import os
from django.conf import settings
import uuid

def download_youtube_video(url):
    """
    Downloads a YouTube stream and returns the absolute system path.
    Fulfills Feature 1: Neural Ingestion Pipeline via Stream Sync.
    """
    # Create a temporary download directory outside of the final media structure if preferred,
    # but here we use the standard MEDIA_ROOT for simplicity.
    output_dir = os.path.join(settings.MEDIA_ROOT, "temp_downloads")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"sync_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(output_dir, filename)

    ydl_opts = {
        # 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' ensures we get an MP4
        'format': 'best[ext=mp4]', 
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        # Adds a timeout to prevent the server from hanging on dead links
        'socket_timeout': 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Return the ABSOLUTE path so the view can do: with open(path, 'rb')
    return output_path
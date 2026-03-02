from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from .models import VideoAnalysis
import os,time

@login_required
def user_dashboard(request):
    """Fulfills Feature 14: Operational Overview for User Node"""
    user_videos = VideoAnalysis.objects.filter(user=request.user)
    recent_videos = user_videos.order_by('-created_at')[:5]
    
    total_bytes = 0
    for video in user_videos:
        if video.video_file:
            try:
                total_bytes += video.video_file.size
            except (ValueError, FileNotFoundError):
                continue
    
    storage_mb = round(total_bytes / (1024 * 1024), 2)
    
    stats = {
        'active_pipelines': user_videos.count(),
        'total_insights': user_videos.count() * 12, 
        'storage_used': f"{storage_mb} MB"
    }

    return render(request, 'videos/dashboard.html', {
        'recent_videos': recent_videos,
        'stats': stats
    })

from .utils import download_youtube_video
from django.core.files import File
from django.conf import settings

@login_required
def upload_video(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        video_file = request.FILES.get('video_file')
        youtube_url = request.POST.get('youtube_url')

        if not video_file and not youtube_url:
            messages.error(request, "No video source provided.")
            return redirect('upload_video')

        if video_file:
            ext = os.path.splitext(video_file.name)[1].lower()
            if ext not in ['.mp4', '.mov', '.avi', '.webm', '.mpeg']:
                messages.error(request, "Invalid video format.")
                return redirect('upload_video')

        video = VideoAnalysis.objects.create(
            user=request.user,
            title=title or "Untitled Node",
            video_file=video_file if video_file else None,
            youtube_url=youtube_url if youtube_url else None
        )

        messages.success(
            request,
            f"Pipeline initialized successfully for: {video.title}"
        )
        return redirect('video_list')

    return render(request, 'videos/upload_video.html')


@login_required
def video_list(request):
    """Fulfills Feature 16: Dynamic Neural Library"""
    if hasattr(request.user, 'role') and request.user.role == 'admin':
        videos = VideoAnalysis.objects.all().order_by('-created_at')
    else:
        videos = VideoAnalysis.objects.filter(user=request.user).order_by('-created_at')
        
    return render(request, 'videos/library.html', {'videos': videos})

@login_required
def delete_video(request, pk):
    video = get_object_or_404(VideoAnalysis, pk=pk)

    # Store path BEFORE deleting DB record
    file_path = None
    if video.video_file:
        file_path = video.video_file.path

    # Delete DB record first
    video.video_file = None
    video.delete()

    # Attempt physical file deletion safely (Windows-safe)
    if file_path and os.path.exists(file_path):
        try:
            time.sleep(0.5)
            os.remove(file_path)
        except PermissionError:
            pass
        except Exception as e:
            print("FILE_DELETE_ERROR:", e)

    messages.success(request, "Neural node terminated successfully.")
    return redirect("video_list")
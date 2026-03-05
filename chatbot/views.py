from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from videos.models import VideoAnalysis, ChatMessage
from django.contrib import messages
import os
import requests

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL_ID = "anthropic/claude-4.5-sonnet"

@login_required
def ai_chatbot_view(request, video_id=None):
    user_videos = VideoAnalysis.objects.filter(user=request.user)

    if not user_videos.exists():
        messages.info(request, "Neural Link Offline: Please process a video to initialize the AI Chatbot.")
        return render(request, 'chatbot/chat_interface.html', {'video': None, 'chat_history': []})

    if video_id:
        video = get_object_or_404(VideoAnalysis, id=video_id, user=request.user)
    else:
        video = user_videos.latest('created_at')

    # Load chat history for this video
    chat_history = ChatMessage.objects.filter(
        video=video, user=request.user
    ).order_by('created_at')

    return render(request, 'chatbot/chat_interface.html', {
        'video': video,
        'chat_history': chat_history
    })


@login_required
def chat_api(request):
    if request.method == "POST":
        user_query = request.POST.get('message', '').strip()
        video_id = request.POST.get('video_id')

        if not user_query:
            return JsonResponse({'response': "Please type a message first."})

        if not video_id:
            return JsonResponse({'response': "PIPELINE_ERROR: No active neural node detected."})

        video = get_object_or_404(VideoAnalysis, id=video_id, user=request.user)

        try:
            is_analyzed = video.summary and "API_STALLED" not in (video.transcript or "")

            objects_str = ', '.join(video.objects_detected) if video.objects_detected else "None detected"
            keywords_str = ', '.join(video.keywords) if video.keywords else "None"

            if is_analyzed:
                system_message = f"""You are a video analysis assistant. You have complete analysis data for a video. Answer any question the user asks using this data.

VIDEO TITLE: {video.title}
SUMMARY: {video.summary}
FULL TRANSCRIPT: {video.transcript}
OBJECTS AND PEOPLE DETECTED: {objects_str}
KEYWORDS: {keywords_str}
ACTIVITY: {video.activity_type}"""

                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL_ID,
                        "max_tokens": 500,
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_query}
                        ]
                    }
                )
            else:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL_ID,
                        "max_tokens": 200,
                        "messages": [
                            {"role": "user", "content": f"Tell user that video '{video.title}' is not yet analyzed. Ask them to process insights first."}
                        ]
                    }
                )

            data = response.json()
            final_answer = data['choices'][0]['message']['content']

            # Save to database
            ChatMessage.objects.create(
                video=video,
                user=request.user,
                user_message=user_query,
                ai_response=final_answer
            )

        except Exception as e:
            print(f"CHAT_CORE_ERROR: {e}")
            final_answer = "Neural link unstable. Please try again shortly."

        return JsonResponse({'response': final_answer})


@login_required
def chat_history_view(request, video_id=None):
    """Shows chat history - all videos list or specific video's chat"""
    # Get all videos that have chat messages for this user
    from videos.models import ChatMessage
    videos_with_chats = VideoAnalysis.objects.filter(
        user=request.user,
        chat_messages__isnull=False
    ).distinct().order_by('-created_at')

    selected_video = None
    selected_chats = []

    if video_id:
        selected_video = get_object_or_404(VideoAnalysis, id=video_id, user=request.user)
        selected_chats = ChatMessage.objects.filter(
            video=selected_video,
            user=request.user
        ).order_by('created_at')

    return render(request, 'chatbot/chat_history.html', {
        'videos_with_chats': videos_with_chats,
        'selected_video': selected_video,
        'selected_chats': selected_chats,
    })
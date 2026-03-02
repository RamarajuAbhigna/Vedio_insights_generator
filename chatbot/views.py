from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from videos.models import VideoAnalysis
from django.contrib import messages
from google import genai  # Modern 2026 SDK
import os

# Configure modern Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_ID = "gemini-3-flash-preview"

@login_required
def ai_chatbot_view(request):
    """Initializes the Chat Interface with the user's latest neural node."""
    user_videos = VideoAnalysis.objects.filter(user=request.user)
    
    if not user_videos.exists():
        messages.info(request, "Neural Link Offline: Please process a video to initialize the AI Chatbot.")
        return render(request, 'chatbot/chat_interface.html', {'video': None})
    
    # Grab the latest analyzed session for immediate chat context
    latest_video = user_videos.latest('created_at')
    return render(request, 'chatbot/chat_interface.html', {'video': latest_video})

@login_required
def chat_api(request):
    """Dynamic RAG logic: Grounding the AI in your specific video database data."""
    if request.method == "POST":
        user_query = request.POST.get('message', '')
        video_id = request.POST.get('video_id')
        
        if not video_id:
            return JsonResponse({'response': "PIPELINE_ERROR: No active neural node detected."})
            
        # Fetch the specific analysis node
        video = get_object_or_404(VideoAnalysis, id=video_id)
        
        try:
            # 1. Check if the video has been analyzed yet
            is_analyzed = video.summary and "API_STALLED" not in (video.transcript or "")
            
            # 2. Format database metadata for the AI's context
            objects_str = ', '.join(video.objects_detected) if video.objects_detected else "Pending scan"
            keywords_str = ', '.join(video.keywords) if video.keywords else "Pending extraction"

            # 3. Build the technical RAG prompt
            if is_analyzed:
                context_payload = f"""
                You are Analysis_Bot_v1.0. Base your answer strictly on this database metadata:
                - VIDEO_TITLE: {video.title}
                - SUMMARY: {video.summary}
                - TRANSCRIPT: {video.transcript}
                - DETECTED_OBJECTS: {objects_str}
                - KEYWORDS: {keywords_str}
                """
            else:
                context_payload = f"""
                The video '{video.title}' is currently in the ingestion pipeline. 
                Deep-sync (AI Analysis) is not yet complete. 
                Answer the user's question politely explaining that full insights are being processed.
                """

            # 4. Execute modern client call
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=f"{context_payload}\n\nUSER_QUERY: {user_query}\n\nINSTRUCTION: Maintain a technical 'Analysis_Bot' tone. Keep response under 60 words."
            )
            
            final_answer = response.text
            
        except Exception as e:
            print(f"CHAT_CORE_ERROR: {e}")
            final_answer = "Neural link unstable. Secondary core suggests checking the 'Insight Library' for static data while deep-sync retries."

        return JsonResponse({'response': final_answer})
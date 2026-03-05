from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.contrib import messages
from videos.models import VideoAnalysis
from django.contrib.auth import get_user_model
from google import genai
import os
import json
import time
import random

User = get_user_model()

# ================= GEMINI CONFIG =================
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_ID = "gemini-3-flash-preview"


def is_admin(user):
    return user.is_authenticated and user.role == 'admin'


# ──────────────────────────────────────────────────────────────
#  VIDEO INSIGHT DETAIL  — crash fix + ML data added
# ──────────────────────────────────────────────────────────────

@login_required
def video_insight_detail(request, pk):
    video = get_object_or_404(VideoAnalysis, pk=pk)

    if not video.ai_processed and not video.ai_failed:
        try:
            if video.video_file:
                uploaded = client.files.upload(file=video.video_file.path)
                while uploaded.state == "PROCESSING":
                    time.sleep(2)
                    uploaded = client.files.get(name=uploaded.name)
                content_source = uploaded

            elif video.youtube_url:
                content_source = video.youtube_url

            else:
                raise ValueError("No valid video source")

            prompt = """
Analyze the ACTUAL visual and audio content of this video.

Return exactly ONE JSON object (no markdown, no extra text):
{
  "transcript": "Real spoken words (~100)",
  "summary": "Two sentence factual summary",
  "keywords": ["tag1","tag2","tag3","tag4","tag5"],
  "objects": ["object1","object2","object3"],
  "activity": "Primary activity seen"
}
"""
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[content_source, prompt]
            )

            raw = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            video.transcript       = data.get("transcript", "")
            video.summary          = data.get("summary", "")
            video.keywords         = data.get("keywords", [])
            video.objects_detected = data.get("objects", [])
            video.activity_type    = data.get("activity", "General")
            video.ai_processed     = True
            video.ai_failed        = False
            video.save()

        except Exception as e:
            print("PIPELINE_ERROR:", e)
            video.transcript   = ""
            video.ai_failed    = True
            video.ai_processed = True
            video.save()

    # ── Run ML models if not done yet ─────────────────────────
    if not video.ml_processed and video.video_file:
        try:
            from videos.ml_analyzer import run_ml_analysis
            video_path = video.video_file.path
            if os.path.exists(video_path):
                ml = run_ml_analysis(video_path, video.transcript or "")
                video.human_presence_data = ml.get("human_presence", {})
                video.face_detection_data = ml.get("face_detection", {})
                video.activity_ml_data    = ml.get("activity", {})
                video.engagement_data     = ml.get("engagement", {})

                # Update activity_type from ML if not already set
                if not video.activity_type or video.activity_type == "General":
                    video.activity_type = ml.get("activity", {}).get("dominant_activity", "General")

                video.ml_processed = True
                video.save()
        except Exception as e:
            print("ML_ERROR:", e)

    # ── DERIVED ANALYTICS ─────────────────────────────────────

    # ✅ FIX: safe transcript — never crashes on None
    safe_transcript = video.transcript or ""

    sentences   = [s.strip() for s in safe_transcript.split(".") if len(s.strip()) > 25]
    key_moments = []

    # Use ML key_moments if available, else derive from transcript
    if hasattr(video, 'key_moments') and video.key_moments:
        try:
            moments = video.key_moments if isinstance(video.key_moments, list) else json.loads(video.key_moments)
            for m in moments[:5]:
                key_moments.append({
                    "time":  m.get("time", m.get("timestamp", "00:00")),
                    "label": m.get("label", m.get("description", ""))[:70]
                })
        except Exception:
            pass

    if not key_moments:
        for i, s in enumerate(sentences[:5]):
            key_moments.append({"time": f"00:{i*20:02d}", "label": s[:70] + "..."})

    word_count   = len(safe_transcript.split()) if safe_transcript else 0
    speech_ratio = min(90, max(60, int(word_count / 2))) if word_count else 60
    silence_ratio = 100 - speech_ratio

    vision_confidence = []
    for idx, obj in enumerate(video.objects_detected or []):
        vision_confidence.append({"label": obj, "confidence": max(55, 100 - idx * 7)})

    # ── ML insight cards ──────────────────────────────────────
    human_presence = video.human_presence_data or {}
    face_detection = video.face_detection_data or {}
    activity_ml    = video.activity_ml_data    or {}

    # Engagement data — use ML result (dict) or fallback to list
    eng_data       = video.engagement_data
    if isinstance(eng_data, dict):
        engagement_wave = eng_data.get("avg_engagement", [])
        engagement_summary = eng_data.get("summary", "")
        engagement_score   = eng_data.get("overall_score", 0)
        engagement_trend   = eng_data.get("trend", "")
    elif isinstance(eng_data, list) and eng_data:
        engagement_wave    = eng_data
        engagement_summary = ""
        engagement_score   = round(sum(eng_data) / len(eng_data), 1)
        engagement_trend   = ""
    else:
        engagement_wave    = []
        engagement_summary = ""
        engagement_score   = 0
        engagement_trend   = ""

    # YouTube embed URL
    video.embed_url = None
    if video.youtube_url:
        if "watch?v=" in video.youtube_url:
            video.embed_url = video.youtube_url.replace("watch?v=", "embed/")
        elif "youtu.be/" in video.youtube_url:
            video.embed_url = video.youtube_url.replace("youtu.be/", "youtube.com/embed/")

    return render(request, "analysis/insight_dashboard.html", {
        "video":              video,
        "key_moments":        key_moments,
        "speech_ratio":       speech_ratio,
        "silence_ratio":      silence_ratio,
        "vision_confidence":  vision_confidence,
        # ── ML Results ──
        "human_presence":     human_presence,
        "face_detection":     face_detection,
        "activity_ml":        activity_ml,
        "engagement_wave":    engagement_wave,
        "engagement_summary": engagement_summary,
        "engagement_score":   engagement_score,
        "engagement_trend":   engagement_trend,
    })


# ──────────────────────────────────────────────────────────────
#  ANALYTICS DASHBOARD (Engagement Hub)  — real ML data
# ──────────────────────────────────────────────────────────────

@login_required
def analytics_dashboard(request):
    user_vids = VideoAnalysis.objects.filter(user=request.user)
    total     = user_vids.count()

    presentation_modes = [
        "Presentation Mode", "Presentation", "Lecture / Teaching",
        "Lecture", "Demo", "Software tutorial", "Tutorial / Demo", "Tutorial"
    ]

    # ── Activity Distribution ─────────────────────────────────
    pres_percent = 0.0
    disc_percent = 0.0

    ml_videos = user_vids.filter(ml_processed=True)

    if ml_videos.exists():
        pres_total = 0.0
        disc_total = 0.0
        valid      = 0

        for vid in ml_videos:
            dist = {}
            if isinstance(vid.activity_ml_data, dict):
                dist = vid.activity_ml_data.get("activity_distribution", {})

            if dist:
                pres_total += (
                    dist.get("Presentation", 0) +
                    dist.get("Lecture / Teaching", 0) +
                    dist.get("Tutorial / Demo", 0)
                )
                disc_total += (
                    dist.get("Meeting / Discussion", 0) +
                    dist.get("Interview", 0) +
                    dist.get("General Activity", 0)
                )
                valid += 1

        if valid:
            pres_percent = round(pres_total / valid, 1)
            disc_percent = round(disc_total / valid, 1)

    else:
        # Fallback to activity_type string matching for old videos
        pres_count   = user_vids.filter(activity_type__in=presentation_modes).count()
        pres_percent = round((pres_count / total * 100), 1) if total > 0 else 0
        disc_percent = round(100 - pres_percent, 1)

    # ── Engagement Wave ───────────────────────────────────────
    TARGET_POINTS = 20
    avg_engagement = []

    all_score_lists = []
    for vid in user_vids:
        eng = vid.engagement_data
        if isinstance(eng, dict):
            scores = eng.get("avg_engagement", [])
            if scores:
                all_score_lists.append(scores)
        elif isinstance(eng, list) and len(eng) > 0:
            all_score_lists.append(eng)

    if all_score_lists:
        # Normalize all to TARGET_POINTS length then average
        resampled = []
        for score_list in all_score_lists:
            if len(score_list) >= TARGET_POINTS:
                resampled.append([int(score_list[i]) for i in range(TARGET_POINTS)])
            else:
                padded = list(score_list) + [int(score_list[-1])] * (TARGET_POINTS - len(score_list))
                resampled.append(padded)

        avg_engagement = [
            int(sum(col) / len(col))
            for col in zip(*resampled)
        ]
    else:
        # No ML data yet — flat line at 0 so panel can see it's waiting for data
        avg_engagement = [0] * TARGET_POINTS

    return render(request, 'analysis/analytics_hub.html', {
        'pres_percent':   pres_percent,
        'disc_percent':   disc_percent,
        'avg_engagement': avg_engagement,
        'total_nodes':    total,
    })


# ──────────────────────────────────────────────────────────────
#  ADMIN VIEWS  (unchanged)
# ──────────────────────────────────────────────────────────────

@user_passes_test(is_admin)
def admin_dashboard(request):
    all_users = User.objects.all().order_by('-date_joined')
    all_vids  = VideoAnalysis.objects.all()
    total     = all_vids.count()
    yt_count  = all_vids.filter(video_file="").count()
    stats = {
        'total_users':   all_users.count(),
        'total_videos':  total,
        'total_insights':total * 12,
        'mp4_percent':   (100 - (yt_count / total * 100)) if total > 0 else 65,
        'yt_percent':    (yt_count / total * 100) if total > 0 else 35
    }
    return render(request, 'admin_dashboard.html', {
        'stats': stats, 'node_users': all_users[:5]
    })


@user_passes_test(is_admin)
def admin_user_management(request):
    node_users = User.objects.annotate(
        video_count=Count('videoanalysis')
    ).order_by('-date_joined')
    return render(request, 'admin_user_management.html', {'node_users': node_users})


@user_passes_test(is_admin)
def admin_toggle_status(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if not target_user.is_superuser:
        target_user.is_active = not target_user.is_active
        target_user.save()
        messages.success(request, f"Identity {target_user.email} status updated.")
    return redirect('admin_user_management')


@user_passes_test(is_admin)
def admin_delete_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if not target_user.is_superuser:
        target_user.delete()
        messages.success(request, "Neural Identity purged.")
    return redirect('admin_user_management')


@user_passes_test(is_admin)
def admin_ai_monitor(request):
    pipeline_health = {
        'vision':    True,
        'speech':    True,
        'analytics': True,
        'logs': [
            "[INFO] System Core Active",
            "[SYSTEM] Monitoring ingress streams..."
        ]
    }
    return render(request, 'admin_ai_monitor.html', {'health': pipeline_health})


@user_passes_test(is_admin)
def admin_analytics(request):
    all_vids = VideoAnalysis.objects.all()
    total    = all_vids.count()
    yt_count = all_vids.filter(video_file="").count()

    global_engagement = [0] * 20
    if total > 0:
        for vid in all_vids:
            data = vid.engagement_data
            if isinstance(data, dict):
                data = data.get("avg_engagement", [0] * 20)
            elif not isinstance(data, list):
                data = [0] * 20
            for i in range(min(len(data), 20)):
                try:
                    global_engagement[i] += int(data[i])
                except Exception:
                    pass
        global_engagement = [int(val / total) for val in global_engagement]

    return render(request, 'admin_analytics.html', {
        'mp4_percent':       100 - (yt_count / total * 100) if total > 0 else 0,
        'yt_percent':        (yt_count / total * 100) if total > 0 else 0,
        'total_count':       total,
        'global_engagement': global_engagement
    })
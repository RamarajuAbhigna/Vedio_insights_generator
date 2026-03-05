from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import io
import os
import time
import json
from .models import VideoAnalysis
from chatbot.models import ChatMessage
from .utils import download_youtube_video, analyze_video_with_gemini   # ← added
from .ml_analyzer import run_ml_analysis                               # ← added
from django.core.files import File
from django.conf import settings


# ──────────────────────────────────────────────────────────────
#  PDF REPORT  (unchanged)
# ──────────────────────────────────────────────────────────────

@login_required
def download_pdf_report(request, video_id):
    video = get_object_or_404(VideoAnalysis, id=video_id, user=request.user)
    chat_messages = ChatMessage.objects.filter(
        video=video, user=request.user
    ).order_by('created_at')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50,
        title=f"{video.title} - Video Insights Report"
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle('ReportTitle', parent=styles['Title'],
        fontSize=22, textColor=colors.HexColor('#1F4E79'),
        spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')
    style_subtitle = ParagraphStyle('SubTitle', parent=styles['Normal'],
        fontSize=11, textColor=colors.HexColor('#666666'),
        spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica')
    style_section = ParagraphStyle('SectionHeading', parent=styles['Heading1'],
        fontSize=13, textColor=colors.white, spaceBefore=14, spaceAfter=8,
        fontName='Helvetica-Bold', backColor=colors.HexColor('#1F4E79'),
        leftIndent=-4, rightIndent=-4, borderPadding=(6, 8, 6, 8))
    style_body = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#222222'),
        fontName='Helvetica', spaceAfter=4, leading=15, alignment=TA_JUSTIFY)
    style_mono = ParagraphStyle('Mono', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#333333'),
        fontName='Courier', spaceAfter=3, leading=14,
        backColor=colors.HexColor('#F5F5F5'),
        leftIndent=8, rightIndent=8, borderPadding=(4, 4, 4, 4))
    style_user_msg = ParagraphStyle('UserMsg', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#1F4E79'),
        fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, leftIndent=10)
    style_ai_msg = ParagraphStyle('AIMsg', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#222222'),
        fontName='Helvetica', spaceAfter=6, leading=14, leftIndent=10,
        backColor=colors.HexColor('#EBF3FA'), borderPadding=(4, 4, 4, 4))

    story = []
    story.append(Paragraph("Video Insights Report", style_title))
    story.append(Paragraph(f"{video.title}", style_subtitle))
    story.append(Paragraph(
        f"Generated on: {video.created_at.strftime('%d %B %Y, %I:%M %p')}",
        style_subtitle))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2,
        color=colors.HexColor('#2E75B6'), spaceAfter=12))

    story.append(Paragraph(" 1.  Summary", style_section))
    story.append(Paragraph(video.summary or "No summary available.", style_body))
    story.append(Spacer(1, 6))

    story.append(Paragraph(" 2.  Keywords & Topics", style_section))
    if video.keywords:
        keywords_text = ', '.join(video.keywords) if isinstance(video.keywords, list) else str(video.keywords)
    else:
        keywords_text = "No keywords extracted."
    story.append(Paragraph(keywords_text, style_body))
    story.append(Spacer(1, 6))

    story.append(Paragraph(" 3.  Objects Detected", style_section))
    if video.objects_detected:
        objects_text = ', '.join(video.objects_detected) if isinstance(video.objects_detected, list) else str(video.objects_detected)
    else:
        objects_text = "No objects detected."
    story.append(Paragraph(objects_text, style_body))
    story.append(Spacer(1, 6))

    story.append(Paragraph(" 4.  Key Moments", style_section))
    if hasattr(video, 'key_moments') and video.key_moments:
        try:
            moments = json.loads(video.key_moments) if isinstance(video.key_moments, str) else video.key_moments
            if isinstance(moments, list):
                for moment in moments:
                    if isinstance(moment, dict):
                        ts   = moment.get('time', moment.get('timestamp', ''))
                        desc = moment.get('label', moment.get('description', ''))
                        story.append(Paragraph(f"<b>{ts}</b> — {desc}", style_body))
                    else:
                        story.append(Paragraph(str(moment), style_body))
            else:
                story.append(Paragraph(str(moments), style_body))
        except Exception:
            story.append(Paragraph(str(video.key_moments), style_body))
    else:
        story.append(Paragraph("No key moments available.", style_body))
    story.append(Spacer(1, 6))

    story.append(Paragraph(" 5.  Full Transcript", style_section))
    transcript = video.transcript or "No transcript available."
    for i in range(0, len(transcript), 1000):
        story.append(Paragraph(transcript[i:i+1000], style_mono))
    story.append(Spacer(1, 6))

    # ── NEW: ML Analysis Section ──
    story.append(Paragraph(" 6.  ML Model Analysis", style_section))

    if video.human_presence_data:
        story.append(Paragraph(f"<b>Human Presence (YOLOv8):</b> {video.human_presence_data.get('summary', '')}", style_body))
    if video.face_detection_data:
        story.append(Paragraph(f"<b>Face Detection (Haar Cascade):</b> {video.face_detection_data.get('summary', '')}", style_body))
    if video.activity_ml_data:
        story.append(Paragraph(f"<b>Activity Recognition (YOLOv8):</b> {video.activity_ml_data.get('summary', '')}", style_body))
    if video.engagement_data:
        eng = video.engagement_data
        if isinstance(eng, dict):
            story.append(Paragraph(f"<b>Engagement Trend (KeyBERT):</b> {eng.get('summary', '')}", style_body))
    story.append(Spacer(1, 6))

    story.append(Paragraph(" 7.  AI Chatbot Conversation", style_section))
    if chat_messages.exists():
        for idx, msg in enumerate(chat_messages, 1):
            ts = msg.created_at.strftime('%d %b %Y, %I:%M %p')
            story.append(Paragraph(f"Q{idx}  [{ts}]  {msg.user_message}", style_user_msg))
            story.append(Paragraph(f"AI:  {msg.ai_response}", style_ai_msg))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No chat conversations for this video.", style_body))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1,
        color=colors.HexColor('#CCCCCC'), spaceAfter=6))
    story.append(Paragraph("Generated by AI-Based Video Insights Generator", style_subtitle))

    doc.build(story)
    buffer.seek(0)

    safe_title = video.title.replace(' ', '_').replace('/', '-')[:50]
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_title}_InsightsReport.pdf"'
    return response


# ──────────────────────────────────────────────────────────────
#  DASHBOARD  (unchanged)
# ──────────────────────────────────────────────────────────────

@login_required
def user_dashboard(request):
    user_videos  = VideoAnalysis.objects.filter(user=request.user)
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
        'total_insights':   user_videos.count() * 12,
        'storage_used':     f"{storage_mb} MB"
    }

    return render(request, 'videos/dashboard.html', {
        'recent_videos': recent_videos,
        'stats': stats
    })


# ──────────────────────────────────────────────────────────────
#  UPLOAD VIDEO  — now calls Gemini + ML models
# ──────────────────────────────────────────────────────────────

@login_required
def upload_video(request):
    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        video_file  = request.FILES.get('video_file')
        youtube_url = request.POST.get('youtube_url')

        if not video_file and not youtube_url:
            messages.error(request, "No video source provided.")
            return redirect('upload_video')

        video = VideoAnalysis.objects.create(
            user=request.user,
            title=title or "Untitled Node"
        )

        if video_file:
            video.video_file = video_file
            video.save()

        elif youtube_url:
            try:
                downloaded_path = download_youtube_video(youtube_url)
                with open(downloaded_path, 'rb') as f:
                    video.video_file.save(f"{video.id}_sync.mp4", File(f), save=True)
                if os.path.exists(downloaded_path):
                    os.remove(downloaded_path)
            except Exception as e:
                video.delete()
                messages.error(request, f"Stream Sync Failed: {str(e)}")
                return redirect('upload_video')

        # ── Step 1: Gemini Analysis ────────────────────────────
        try:
            gemini_results = analyze_video_with_gemini(video.video_file.path)
            video.transcript      = gemini_results.get("transcript", "")
            video.summary         = gemini_results.get("summary", "")
            video.keywords        = gemini_results.get("keywords", [])
            video.objects_detected= gemini_results.get("objects_detected", [])
            video.key_moments     = gemini_results.get("key_moments", [])
            video.activity_type   = gemini_results.get("activity_type", "General Analysis")
            video.ai_processed    = True
            video.save()
        except Exception as e:
            video.ai_failed = True
            video.save()
            messages.warning(request, f"Gemini analysis failed: {str(e)}")

        # ── Step 2: Local ML Models ────────────────────────────
        try:
            video_path = video.video_file.path
            if os.path.exists(video_path) and not video.ml_processed:
                ml_results = run_ml_analysis(
                    video_path=video_path,
                    transcript=video.transcript or ""
                )
                video.human_presence_data = ml_results.get("human_presence", {})
                video.face_detection_data = ml_results.get("face_detection", {})
                video.activity_ml_data    = ml_results.get("activity", {})
                video.engagement_data     = ml_results.get("engagement", {})

                # Also update activity_type from ML if Gemini didn't set it
                if not video.activity_type or video.activity_type == "General Analysis":
                    video.activity_type = ml_results.get("activity", {}).get("dominant_activity", "General Analysis")

                video.ml_processed = True
                video.save()
        except Exception as e:
            messages.warning(request, f"ML analysis failed: {str(e)}")

        messages.success(request, f"Pipeline initialized: {video.title}")
        return redirect('video_list')

    return render(request, 'videos/upload_video.html')


# ──────────────────────────────────────────────────────────────
#  VIDEO LIST  (unchanged)
# ──────────────────────────────────────────────────────────────

@login_required
def video_list(request):
    if hasattr(request.user, 'role') and request.user.role == 'admin':
        videos = VideoAnalysis.objects.all().order_by('-created_at')
    else:
        videos = VideoAnalysis.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'videos/library.html', {'videos': videos})


# ──────────────────────────────────────────────────────────────
#  DELETE VIDEO  (unchanged)
# ──────────────────────────────────────────────────────────────

@login_required
def delete_video(request, pk):
    video     = get_object_or_404(VideoAnalysis, pk=pk)
    file_path = video.video_file.path if video.video_file else None

    video.video_file = None
    video.delete()

    if file_path and os.path.exists(file_path):
        try:
            time.sleep(0.5)
            os.remove(file_path)
        except Exception as e:
            print("FILE_DELETE_ERROR:", e)

    messages.success(request, "Neural node terminated successfully.")
    return redirect("video_list")


# ──────────────────────────────────────────────────────────────
#  ENGAGEMENT HUB  — NEW VIEW (powers your engagement template)
# ──────────────────────────────────────────────────────────────

@login_required
def engagement_hub(request):
    """
    Powers the Engagement Hub page.
    Aggregates activity distribution + engagement scores across ALL user videos.
    """
    user_videos = VideoAnalysis.objects.filter(
        user=request.user,
        ml_processed=True
    )

    total_nodes   = user_videos.count()
    pres_percent  = 0.0
    disc_percent  = 0.0
    avg_engagement= []

    if total_nodes > 0:
        # ── Activity Distribution (aggregate across all videos) ──
        pres_total = 0.0
        disc_total = 0.0
        valid_act  = 0

        for v in user_videos:
            dist = {}
            if isinstance(v.activity_ml_data, dict):
                dist = v.activity_ml_data.get("activity_distribution", {})
            elif isinstance(v.activity_type, str):
                # fallback: treat activity_type as 100% of one category
                dist = {v.activity_type: 100}

            if dist:
                pres_total += dist.get("Presentation", 0) + dist.get("Lecture / Teaching", 0)
                disc_total += dist.get("Meeting / Discussion", 0) + dist.get("Tutorial / Demo", 0)
                valid_act  += 1

        if valid_act:
            pres_percent = round(pres_total / valid_act, 1)
            disc_percent = round(disc_total / valid_act, 1)

        # ── Engagement Bars (average score per segment across all videos) ──
        all_score_lists = []
        for v in user_videos:
            eng = v.engagement_data
            if isinstance(eng, dict):
                scores = eng.get("avg_engagement", [])
                if scores:
                    all_score_lists.append(scores)
            elif isinstance(eng, list) and eng:
                all_score_lists.append(eng)

        if all_score_lists:
            # Normalize all lists to same length (16 bars) then average
            n_bars    = 16
            resampled = []
            for score_list in all_score_lists:
                if len(score_list) >= n_bars:
                    resampled.append(score_list[:n_bars])
                else:
                    # pad with last value
                    padded = score_list + [score_list[-1]] * (n_bars - len(score_list))
                    resampled.append(padded)

            avg_engagement = [
                round(sum(col) / len(col), 1)
                for col in zip(*resampled)
            ]

    return render(request, 'videos/engagement_hub.html', {
        'pres_percent':   pres_percent,
        'disc_percent':   disc_percent,
        'avg_engagement': avg_engagement,
        'total_nodes':    total_nodes,
    })
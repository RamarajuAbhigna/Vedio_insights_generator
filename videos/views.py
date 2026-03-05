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
from .utils import download_youtube_video
from django.core.files import File
from django.conf import settings


@login_required
def download_pdf_report(request, video_id):
    # ── fetch data ──────────────────────────────────────────
    video = get_object_or_404(VideoAnalysis, id=video_id, user=request.user)
    chat_messages = ChatMessage.objects.filter(
        video=video, user=request.user
    ).order_by('created_at')

    # ── set up PDF buffer ───────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
        title=f"{video.title} - Video Insights Report"
    )

    # ── define styles ───────────────────────────────────────
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=22,
        textColor=colors.HexColor('#1F4E79'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    style_subtitle = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )

    style_section = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading1'],
        fontSize=13,
        textColor=colors.white,
        spaceBefore=14,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#1F4E79'),
        leftIndent=-4,
        rightIndent=-4,
        borderPadding=(6, 8, 6, 8),
    )

    style_label = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#2E75B6'),
        fontName='Helvetica-Bold',
        spaceBefore=6,
        spaceAfter=2,
    )

    style_body = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#222222'),
        fontName='Helvetica',
        spaceAfter=4,
        leading=15,
        alignment=TA_JUSTIFY,
    )

    style_mono = ParagraphStyle(
        'Mono',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#333333'),
        fontName='Courier',
        spaceAfter=3,
        leading=14,
        backColor=colors.HexColor('#F5F5F5'),
        leftIndent=8,
        rightIndent=8,
        borderPadding=(4, 4, 4, 4),
    )

    style_user_msg = ParagraphStyle(
        'UserMsg',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1F4E79'),
        fontName='Helvetica-Bold',
        spaceBefore=8,
        spaceAfter=2,
        leftIndent=10,
    )

    style_ai_msg = ParagraphStyle(
        'AIMsg',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#222222'),
        fontName='Helvetica',
        spaceAfter=6,
        leading=14,
        leftIndent=10,
        backColor=colors.HexColor('#EBF3FA'),
        borderPadding=(4, 4, 4, 4),
    )

    # ── build content ───────────────────────────────────────
    story = []

    # ── HEADER ──
    story.append(Paragraph("Video Insights Report", style_title))
    story.append(Paragraph(f"{video.title}", style_subtitle))
    story.append(Paragraph(
        f"Generated on: {video.created_at.strftime('%d %B %Y, %I:%M %p')}",
        style_subtitle
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.HexColor('#2E75B6'), spaceAfter=12
    ))

    # ── SECTION 1: SUMMARY ──
    story.append(Paragraph(" 1.  Summary", style_section))
    summary_text = video.summary if video.summary else "No summary available."
    story.append(Paragraph(summary_text, style_body))
    story.append(Spacer(1, 6))

    # ── SECTION 2: KEYWORDS ──
    story.append(Paragraph(" 2.  Keywords & Topics", style_section))
    # ✅ FIX: keywords is a JSON list, join to string
    if video.keywords:
        if isinstance(video.keywords, list):
            keywords_text = ', '.join(video.keywords)
        else:
            keywords_text = str(video.keywords)
    else:
        keywords_text = "No keywords extracted."
    story.append(Paragraph(keywords_text, style_body))
    story.append(Spacer(1, 6))

    # ── SECTION 3: OBJECTS DETECTED ──
    story.append(Paragraph(" 3.  Objects Detected", style_section))
    # ✅ FIX: objects_detected is a JSON list, join to string
    if video.objects_detected:
        if isinstance(video.objects_detected, list):
            objects_text = ', '.join(video.objects_detected)
        else:
            objects_text = str(video.objects_detected)
    else:
        objects_text = "No objects detected."
    story.append(Paragraph(objects_text, style_body))
    story.append(Spacer(1, 6))

    # ── SECTION 4: KEY MOMENTS ──
    story.append(Paragraph(" 4.  Key Moments", style_section))
    if hasattr(video, 'key_moments') and video.key_moments:
        try:
            moments = json.loads(video.key_moments) if isinstance(video.key_moments, str) else video.key_moments
            if isinstance(moments, list):
                for moment in moments:
                    if isinstance(moment, dict):
                        # ✅ FIX: use 'time' and 'label' instead of 'timestamp' and 'description'
                        ts = moment.get('time', moment.get('timestamp', ''))
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

    # ── SECTION 5: FULL TRANSCRIPT ──
    story.append(Paragraph(" 5.  Full Transcript", style_section))
    transcript = video.transcript if video.transcript else "No transcript available."
    chunk_size = 1000
    for i in range(0, len(transcript), chunk_size):
        chunk = transcript[i:i + chunk_size]
        story.append(Paragraph(chunk, style_mono))
    story.append(Spacer(1, 6))

    # ── SECTION 6: CHAT HISTORY ──
    story.append(Paragraph(" 6.  AI Chatbot Conversation", style_section))
    if chat_messages.exists():
        for idx, msg in enumerate(chat_messages, 1):
            ts = msg.created_at.strftime('%d %b %Y, %I:%M %p')
            story.append(Paragraph(
                f"Q{idx}  [{ts}]  {msg.user_message}",
                style_user_msg
            ))
            story.append(Paragraph(
                f"AI:  {msg.ai_response}",
                style_ai_msg
            ))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No chat conversations for this video.", style_body))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor('#CCCCCC'), spaceAfter=6
    ))
    story.append(Paragraph(
        "Generated by AI-Based Video Insights Generator",
        style_subtitle
    ))

    # ── build PDF ───────────────────────────────────────────
    doc.build(story)
    buffer.seek(0)

    # ── return as download ──────────────────────────────────
    safe_title = video.title.replace(' ', '_').replace('/', '-')[:50]
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_title}_InsightsReport.pdf"'
    return response


@login_required
def user_dashboard(request):
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


@login_required
def upload_video(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        video_file = request.FILES.get('video_file')
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
                    django_file = File(f)
                    video.video_file.save(f"{video.id}_sync.mp4", django_file, save=True)
                if os.path.exists(downloaded_path):
                    os.remove(downloaded_path)
            except Exception as e:
                video.delete()
                messages.error(request, f"Stream Sync Failed: {str(e)}")
                return redirect('upload_video')

        messages.success(request, f"Pipeline initialized: {video.title}")
        return redirect('video_list')

    return render(request, 'videos/upload_video.html')


@login_required
def video_list(request):
    if hasattr(request.user, 'role') and request.user.role == 'admin':
        videos = VideoAnalysis.objects.all().order_by('-created_at')
    else:
        videos = VideoAnalysis.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'videos/library.html', {'videos': videos})


@login_required
def delete_video(request, pk):
    video = get_object_or_404(VideoAnalysis, pk=pk)

    file_path = None
    if video.video_file:
        file_path = video.video_file.path

    video.video_file = None
    video.delete()

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
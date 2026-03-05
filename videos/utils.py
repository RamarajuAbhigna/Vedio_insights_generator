import yt_dlp
import os
import json
import uuid
from django.conf import settings


# ──────────────────────────────────────────────────────────────
#  YOUTUBE DOWNLOADER  (unchanged)
# ──────────────────────────────────────────────────────────────

def download_youtube_video(url):
    """
    Downloads a YouTube stream and returns the absolute system path.
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, "temp_downloads")
    os.makedirs(output_dir, exist_ok=True)

    filename    = f"sync_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(output_dir, filename)

    ydl_opts = {
        'format':         'best[ext=mp4]',
        'outtmpl':        output_path,
        'quiet':          True,
        'no_warnings':    True,
        'socket_timeout': 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return output_path


# ──────────────────────────────────────────────────────────────
#  GEMINI VIDEO ANALYSIS  — NEW
# ──────────────────────────────────────────────────────────────

def analyze_video_with_gemini(video_path: str) -> dict:
    """
    Sends the video file to Gemini Vision API for multi-modal analysis.
    Returns a structured dict with all insight fields.

    Called from views.py → upload_video() after file is saved.
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    client  = genai.Client(api_key=api_key)

    # ── Upload video file to Gemini Files API ──────────────────
    print(f"[GEMINI] Uploading video: {video_path}")
    video_file = client.files.upload(file=video_path)

    # Wait until Gemini finishes processing the file
    import time
    while video_file.state.name == "PROCESSING":
        time.sleep(3)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file processing failed: {video_file.state.name}")

    print("[GEMINI] File ready. Running analysis...")

    # ── Structured prompt ──────────────────────────────────────
    prompt = """
Analyze this video thoroughly and return ONLY a valid JSON object (no markdown, no extra text).

The JSON must have exactly these keys:

{
  "transcript": "Full verbatim speech-to-text transcript of everything spoken in the video.",
  "summary": "A 3-5 sentence professional summary of the video content.",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "objects_detected": ["object1", "object2", "object3"],
  "activity_type": "One of: Lecture, Presentation, Meeting, Tutorial, Interview, Discussion, General",
  "key_moments": [
    {"time": "0:30", "label": "Brief description of what happens at this moment"},
    {"time": "1:45", "label": "Brief description"},
    {"time": "3:10", "label": "Brief description"}
  ]
}

Rules:
- transcript must be the actual spoken words, not a description
- keywords must be a JSON array of strings
- objects_detected must be a JSON array of strings
- key_moments must be a JSON array of objects with 'time' and 'label' keys
- activity_type must be a single string
- Return ONLY the JSON object, nothing else
"""

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[video_file, prompt]
    )

    raw_text = response.text.strip()

    # ── Parse JSON response ────────────────────────────────────
    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines    = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback: return partial data so upload doesn't fully fail
        print(f"[GEMINI] JSON parse failed. Raw: {raw_text[:300]}")
        result = {
            "transcript":      raw_text,
            "summary":         "Analysis completed. See transcript for details.",
            "keywords":        [],
            "objects_detected":[],
            "activity_type":   "General",
            "key_moments":     []
        }

    # ── Clean up uploaded file from Gemini servers ─────────────
    try:
        client.files.delete(name=video_file.name)
    except Exception:
        pass

    print("[GEMINI] Analysis complete.")
    return result
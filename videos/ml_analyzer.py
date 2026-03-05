"""
VideoInsights ML Analyzer
=========================
Local ML Models for 4 missing features:
  - Feature 6:  Human Presence Detection  → YOLOv8 Nano (COCO dataset)
  - Feature 7:  Face Detection            → OpenCV Haar Cascade (Viola-Jones)
  - Feature 8:  Activity Recognition      → YOLOv8 + multi-signal classifier
  - Feature 11: Engagement Trend          → KeyBERT (BERT embeddings)
"""

import cv2
import numpy as np
import os


_yolo_model   = None
_face_cascade = None

def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8n.pt")
    return _yolo_model

def _get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(path)
    return _face_cascade


# ──────────────────────────────────────────────────────────────
#  FRAME SAMPLER
# ──────────────────────────────────────────────────────────────

def sample_frames(video_path: str, max_frames: int = 40):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total    = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps      = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration = total / fps
    count    = min(max_frames, max(total, 1))
    indices  = np.linspace(0, total - 1, count, dtype=int)

    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if ret:
            frames.append((int(idx), round(idx / fps, 2), frame))

    cap.release()
    return frames, duration


# ──────────────────────────────────────────────────────────────
#  FEATURE 6 — HUMAN PRESENCE DETECTION
# ──────────────────────────────────────────────────────────────

def detect_human_presence(frames: list, duration: float):
    model         = _get_yolo()
    present_count = 0
    timeline      = []

    for idx, ts, frame in frames:
        results    = model(frame, classes=[0], verbose=False, conf=0.35)
        n_persons  = len(results[0].boxes) if results[0].boxes else 0
        is_present = n_persons > 0
        if is_present:
            present_count += 1
        timeline.append({"ts": ts, "present": is_present, "count": n_persons})

    ratio        = present_count / len(frames) if frames else 0.0
    present_secs = round(ratio * duration, 1)
    absent_secs  = round(duration - present_secs, 1)

    return {
        "presence_ratio":  round(ratio, 3),
        "present_seconds": present_secs,
        "absent_seconds":  absent_secs,
        "total_duration":  round(duration, 1),
        "timeline":        timeline,
        "summary": (
            f"Human presence detected in {ratio*100:.1f}% of the video "
            f"({present_secs}s present, {absent_secs}s absent out of {round(duration,1)}s total)."
        )
    }


# ──────────────────────────────────────────────────────────────
#  FEATURE 7 — FACE DETECTION
# ──────────────────────────────────────────────────────────────

def detect_faces(frames: list, duration: float):
    cascade        = _get_face_cascade()
    frames_w_faces = 0
    total_faces    = 0
    max_faces      = 0
    timeline       = []

    for idx, ts, frame in frames:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray  = cv2.equalizeHist(gray)
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=4, minSize=(20, 20)
        )
        n = len(faces)
        total_faces += n
        max_faces    = max(max_faces, n)
        if n > 0:
            frames_w_faces += 1
        timeline.append({"ts": ts, "face_count": n})

    ratio     = frames_w_faces / len(frames) if frames else 0.0
    avg_faces = total_faces / len(frames) if frames else 0.0
    face_secs = round(ratio * duration, 1)

    return {
        "face_detected_ratio":     round(ratio, 3),
        "avg_faces_per_frame":     round(avg_faces, 2),
        "max_faces_in_frame":      max_faces,
        "face_visibility_seconds": face_secs,
        "total_duration":          round(duration, 1),
        "timeline":                timeline,
        "summary": (
            f"Faces visible in {ratio*100:.1f}% of the video. "
            f"Average {avg_faces:.1f} face(s) per frame; "
            f"peak of {max_faces} face(s) detected simultaneously."
        )
    }


# ──────────────────────────────────────────────────────────────
#  FEATURE 8 — ACTIVITY RECOGNITION  (multi-signal)
# ──────────────────────────────────────────────────────────────

def _has_large_person(person_boxes: list, w: int, h: int) -> bool:
    """True if any person box covers more than 8% of the frame — means close to camera."""
    if not person_boxes or w == 0 or h == 0:
        return False
    frame_area = w * h
    for x1, y1, x2, y2 in person_boxes:
        if ((x2 - x1) * (y2 - y1)) / frame_area > 0.08:
            return True
    return False


def _score_activity(detected: set, n_persons: int, n_faces: int,
                    motion: float, w: int, h: int, person_boxes: list) -> dict:
    """
    Score each activity based on multiple signals.
    Returns dict of {activity: score}. Higher = more likely.
    """
    scores = {
        "Lecture / Teaching":   0.0,
        "Presentation":         0.0,
        "Meeting / Discussion": 0.0,
        "Tutorial / Demo":      0.0,
        "Interview":            0.0,
        "Screen Recording":     0.0,
        "Physical Activity":    0.0,
        "Idle / No Activity":   0.0,
    }

    # COCO class flags
    has_person   = 0  in detected
    has_monitor  = 62 in detected
    has_laptop   = 63 in detected
    has_keyboard = 66 in detected
    has_mouse    = 64 in detected
    has_chair    = 56 in detected
    has_couch    = 57 in detected
    has_book     = 73 in detected
    has_phone    = 67 in detected
    has_table    = 60 in detected
    has_bottle   = 39 in detected
    has_sports   = 32 in detected

    multi_person = n_persons >= 2
    large_person = _has_large_person(person_boxes, w, h)
    high_motion  = motion > 40
    low_motion   = motion < 15

    # ── No person present ─────────────────────────────────────
    if not has_person:
        if has_monitor or has_laptop or has_keyboard:
            scores["Screen Recording"] = 80.0
        else:
            scores["Idle / No Activity"] = 70.0
        return scores

    # ── Screen Recording (person barely visible) ──────────────
    if has_monitor and has_keyboard and has_mouse and not multi_person:
        scores["Screen Recording"] += 30.0

    # ── Lecture / Teaching ────────────────────────────────────
    # Signals: person + monitor OR book, single person, low motion
    if has_monitor or has_book:
        scores["Lecture / Teaching"] += 35.0
    if has_monitor and has_book:
        scores["Lecture / Teaching"] += 20.0
    if not multi_person and low_motion:
        scores["Lecture / Teaching"] += 15.0
    if large_person and not multi_person:
        scores["Lecture / Teaching"] += 10.0

    # ── Presentation ──────────────────────────────────────────
    # Signals: person + monitor + laptop together, single presenter
    if has_monitor and has_laptop:
        scores["Presentation"] += 55.0
        if has_keyboard:
            scores["Presentation"] += 10.0
        if not multi_person:
            scores["Presentation"] += 10.0
        if low_motion:
            scores["Presentation"] += 5.0
    elif has_monitor and not has_laptop:
        scores["Presentation"] += 20.0

    # ── Tutorial / Demo ───────────────────────────────────────
    # Signals: person + laptop + keyboard/mouse (typing/clicking demo)
    if has_laptop and (has_keyboard or has_mouse):
        scores["Tutorial / Demo"] += 50.0
        if has_monitor:
            scores["Tutorial / Demo"] += 10.0
        if not high_motion and not low_motion:
            scores["Tutorial / Demo"] += 10.0  # moderate = typing

    # Single person close to camera + phone = mobile tutorial
    if large_person and has_phone and not multi_person:
        scores["Tutorial / Demo"] += 20.0

    # ── Meeting / Discussion ──────────────────────────────────
    # Signals: multiple people, chairs/table, low motion
    if multi_person:
        scores["Meeting / Discussion"] += 45.0
        if has_chair or has_table:
            scores["Meeting / Discussion"] += 20.0
        if has_laptop or has_phone:
            scores["Meeting / Discussion"] += 10.0
        if low_motion:
            scores["Meeting / Discussion"] += 10.0
        if has_bottle or has_couch:
            scores["Meeting / Discussion"] += 5.0
    elif has_chair and has_table and not multi_person:
        scores["Meeting / Discussion"] += 15.0

    # ── Interview ─────────────────────────────────────────────
    # STRICT: needs multiple people + chair + low motion + NO tech
    # This prevents single-person videos from being classified as interview
    no_tech = not has_monitor and not has_laptop and not has_keyboard
    if multi_person and has_chair and low_motion and no_tech:
        scores["Interview"] += 55.0
        if n_faces >= 2:
            scores["Interview"] += 20.0
    elif multi_person and n_faces >= 2 and no_tech and low_motion:
        scores["Interview"] += 40.0
    # Single person alone → NOT an interview (remove old fallback)
    # Only multi-person scenarios get interview label

    # ── Physical Activity ─────────────────────────────────────
    if high_motion and has_person:
        no_desk = not has_laptop and not has_monitor and not has_keyboard
        if no_desk:
            scores["Physical Activity"] += 45.0
        if has_sports:
            scores["Physical Activity"] += 30.0
        if multi_person:
            scores["Physical Activity"] += 10.0

    # ── Idle ─────────────────────────────────────────────────
    if low_motion and not has_monitor and not has_laptop and not multi_person and not large_person:
        scores["Idle / No Activity"] += 25.0

    # ── Talking head (single person, large, no tech, moderate motion) ──
    # This is the most common YouTube/tutorial/vlog scenario
    if large_person and not multi_person and not has_monitor and not has_laptop:
        if not low_motion:
            scores["Tutorial / Demo"] += 25.0  # talking + gesturing
        else:
            scores["Lecture / Teaching"] += 15.0

    return scores


def recognize_activity(frames: list, duration: float):
    model        = _get_yolo()
    cascade      = _get_face_cascade()
    frame_labels = []
    counts       = {}
    prev_gray    = None
    motion       = 30.0

    for idx, ts, frame in frames:
        h, w = frame.shape[:2]

        # YOLO
        results      = model(frame, verbose=False, conf=0.30)
        classes      = set()
        n_persons    = 0
        person_boxes = []

        if results[0].boxes:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                classes.add(cls)
                if cls == 0:
                    n_persons += 1
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    person_boxes.append((x1, y1, x2, y2))

        # Face detection
        gray_f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_eq = cv2.equalizeHist(gray_f)
        faces   = cascade.detectMultiScale(gray_eq, scaleFactor=1.05, minNeighbors=4, minSize=(20, 20))
        n_faces = len(faces)

        # Motion
        if prev_gray is not None:
            motion = float(np.mean(cv2.absdiff(gray_f, prev_gray)))
        prev_gray = gray_f

        # Score and pick best activity
        act_scores   = _score_activity(classes, n_persons, n_faces, motion, w, h, person_boxes)
        best_activity = max(act_scores, key=act_scores.get)
        best_score    = act_scores[best_activity]

        if best_score < 15.0:
            best_activity = "General Activity"

        frame_labels.append({"ts": ts, "activity": best_activity})
        counts[best_activity] = counts.get(best_activity, 0) + 1

    total    = sum(counts.values()) or 1
    dominant = max(counts, key=counts.get) if counts else "Unknown"
    dist     = {k: round(v / total * 100, 1) for k, v in counts.items() if v > 0}

    segments = []
    if frame_labels:
        s_start = frame_labels[0]["ts"]
        s_act   = frame_labels[0]["activity"]
        for i in range(1, len(frame_labels)):
            if frame_labels[i]["activity"] != s_act:
                segments.append({"start": s_start, "end": frame_labels[i]["ts"], "activity": s_act})
                s_start = frame_labels[i]["ts"]
                s_act   = frame_labels[i]["activity"]
        segments.append({"start": s_start, "end": duration, "activity": s_act})

    return {
        "dominant_activity":     dominant,
        "activity_distribution": dist,
        "segments":              segments,
        "summary": (
            f"Dominant activity: '{dominant}'. "
            + " | ".join(f"{k}: {v}%" for k, v in sorted(dist.items(), key=lambda x: -x[1]))
        )
    }


# ──────────────────────────────────────────────────────────────
#  FEATURE 11 — ENGAGEMENT TREND
# ──────────────────────────────────────────────────────────────

def analyze_engagement(transcript: str, frames: list, duration: float):
    n_segments   = max(6, min(16, int(duration / 30)))
    seg_duration = duration / n_segments

    text_scores   = _score_transcript(transcript, n_segments)
    visual_scores = _score_motion(frames, n_segments, duration)

    segments = []
    for i in range(n_segments):
        t = text_scores[i]  if i < len(text_scores)   else 50.0
        v = visual_scores[i] if i < len(visual_scores) else 50.0
        combined = round(min(100, max(5, t * 0.6 + v * 0.4)), 1)
        segments.append({
            "start": round(i * seg_duration, 1),
            "end":   round((i + 1) * seg_duration, 1),
            "score": combined,
            "label": _eng_label(combined)
        })

    scores_only = [s["score"] for s in segments]
    overall     = round(sum(scores_only) / len(scores_only), 1)
    trend       = _compute_trend(scores_only)

    return {
        "overall_score":  overall,
        "trend":          trend,
        "segments":       segments,
        "chart_data":     {"labels": [f"{int(s['start'])}s" for s in segments], "scores": scores_only},
        "avg_engagement": scores_only,
        "summary": (
            f"Overall engagement: {overall}/100 ({_eng_label(overall)}). "
            f"Trend: {trend}. "
            f"Peak at {int(segments[scores_only.index(max(scores_only))]['start'])}s "
            f"with score {max(scores_only)}."
        )
    }


def _score_transcript(transcript: str, n: int) -> list:
    if not transcript or len(transcript.strip()) < 20:
        return [50.0] * n
    try:
        from keybert import KeyBERT
        kw_model = KeyBERT()
        words    = transcript.split()
        seg_size = max(1, len(words) // n)
        scores   = []
        for i in range(n):
            chunk = " ".join(words[i * seg_size:(i + 1) * seg_size])
            if len(chunk.strip()) < 10:
                scores.append(50.0)
                continue
            kws = kw_model.extract_keywords(chunk, keyphrase_ngram_range=(1, 2), stop_words="english", top_n=5)
            scores.append(round(sum(s for _, s in kws) / len(kws) * 100, 1) if kws else 30.0)
        return scores
    except ImportError:
        return _score_transcript_simple(transcript, n)


def _score_transcript_simple(transcript: str, n: int) -> list:
    import re
    sents    = [s.strip() for s in re.split(r'[.!?]+', transcript) if len(s.strip()) > 5]
    if not sents:
        return [50.0] * n
    seg_size = max(1, len(sents) // n)
    scores   = []
    for i in range(n):
        chunk = sents[i * seg_size:(i + 1) * seg_size]
        if not chunk:
            scores.append(50.0)
            continue
        words = " ".join(chunk).lower().split()
        unique_ratio = len(set(words)) / max(len(words), 1)
        avg_len      = sum(len(s.split()) for s in chunk) / len(chunk)
        scores.append(round(unique_ratio * 60 + min(avg_len, 20) / 20 * 40, 1))
    return scores


def _score_motion(frames: list, n: int, duration: float) -> list:
    if len(frames) < 2:
        return [50.0] * n
    pts       = []
    prev_gray = None
    for idx, ts, frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            pts.append((ts, min(100, float(np.mean(cv2.absdiff(gray, prev_gray))) / 25 * 100)))
        prev_gray = gray
    seg_dur = duration / n
    return [
        round(sum(s for t, s in pts if i * seg_dur <= t < (i + 1) * seg_dur) /
              max(len([s for t, s in pts if i * seg_dur <= t < (i + 1) * seg_dur]), 1), 1)
        for i in range(n)
    ]


def _eng_label(score: float) -> str:
    if score >= 75: return "High"
    if score >= 50: return "Moderate"
    if score >= 25: return "Low"
    return "Very Low"


def _compute_trend(scores: list) -> str:
    if len(scores) < 3:
        return "Stable"
    mid  = len(scores) // 2
    f    = sum(scores[:mid]) / mid
    s    = sum(scores[mid:]) / (len(scores) - mid)
    std  = float(np.std(scores))
    if std > 20:       return "Mixed"
    if s - f > 8:      return "Increasing"
    if f - s > 8:      return "Decreasing"
    return "Stable"


# ──────────────────────────────────────────────────────────────
#  MASTER RUNNER
# ──────────────────────────────────────────────────────────────

def run_ml_analysis(video_path: str, transcript: str = ""):
    results = {"errors": {}}

    try:
        frames, duration = sample_frames(video_path, max_frames=40)
    except Exception as e:
        return {"human_presence": {}, "face_detection": {}, "activity": {}, "engagement": {}, "errors": {"frame_sampling": str(e)}}

    try:
        results["human_presence"] = detect_human_presence(frames, duration)
    except Exception as e:
        results["human_presence"] = {"summary": "Analysis unavailable.", "presence_ratio": 0, "present_seconds": 0, "absent_seconds": 0}
        results["errors"]["human_presence"] = str(e)

    try:
        results["face_detection"] = detect_faces(frames, duration)
    except Exception as e:
        results["face_detection"] = {"summary": "Analysis unavailable.", "face_detected_ratio": 0, "max_faces_in_frame": 0, "avg_faces_per_frame": 0}
        results["errors"]["face_detection"] = str(e)

    try:
        results["activity"] = recognize_activity(frames, duration)
    except Exception as e:
        results["activity"] = {"summary": "Analysis unavailable.", "dominant_activity": "Unknown", "activity_distribution": {}}
        results["errors"]["activity"] = str(e)

    try:
        results["engagement"] = analyze_engagement(transcript, frames, duration)
    except Exception as e:
        results["engagement"] = {"summary": "Analysis unavailable.", "overall_score": 0, "trend": "Unknown", "avg_engagement": []}
        results["errors"]["engagement"] = str(e)

    return results
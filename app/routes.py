import base64
import csv
import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import qrcode
from flask import Blueprint, Response, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import User
from app import supabase_client as supa

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except Exception:
    cv2 = None
    np = None
    CV_AVAILABLE = False

main_bp = Blueprint("main", __name__)

ANTI_SPOOF_CHALLENGES = [
    "Blink twice, then turn your face slightly to the left.",
    "Look at camera, smile, then turn your face slightly to the right.",
    "Raise your eyebrows once, then move your head a little forward.",
    "Look straight, blink once, then tilt head slightly upward.",
]
LIVENESS_THRESHOLD = 3.0
FACE_MATCH_THRESHOLD = 0.55
RECORDS_PER_PAGE = 15


# ---------------------------------------------------------------------------
# Role decorators
# ---------------------------------------------------------------------------

def teacher_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_teacher:
            abort(403)
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapped


def student_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_student:
            abort(403)
        return f(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc():
    return datetime.now(timezone.utc)


def _session_is_expired(session_row):
    exp = session_row.get("expires_at", "")
    if isinstance(exp, str):
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        except Exception:
            return True
    else:
        exp_dt = exp
    return exp_dt < _now_utc()


def _deactivate_expired_sessions():
    active = supa.get_active_sessions()
    for s in active:
        if _session_is_expired(s):
            supa.update_session(s["id"], {"is_active": False})


def _to_data_url_png(payload: str) -> str:
    qr_img = qrcode.make(payload)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _decode_image_from_data_url(data_url: str):
    if not data_url or "," not in data_url:
        raise ValueError("Invalid image payload.")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    image_hash = hashlib.sha256(raw).hexdigest()
    if not CV_AVAILABLE:
        raise RuntimeError("OpenCV is unavailable.")
    nparr = np.frombuffer(raw, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image frame.")
    return frame, image_hash


def _calc_attendance_pct(student_id):
    total = supa.count_closed_sessions()
    if total == 0:
        return 0.0
    attended = supa.count_records_for_student(student_id)
    return round((attended / total) * 100, 1)


# ---------------------------------------------------------------------------
# Face detection & recognition (unchanged)
# ---------------------------------------------------------------------------

def _detect_faces(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(70, 70))
    return faces, gray


def _primary_face_roi(frame):
    faces, gray = _detect_faces(frame)
    if len(faces) < 1:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return gray[y : y + h, x : x + w]


def _face_signature(face_roi):
    resized = cv2.resize(face_roi, (128, 128))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    norm = clahe.apply(resized)
    grid_size = 4
    cell_h = norm.shape[0] // grid_size
    cell_w = norm.shape[1] // grid_size
    signature = []
    for row in range(grid_size):
        for col in range(grid_size):
            cell = norm[row * cell_h : (row + 1) * cell_h, col * cell_w : (col + 1) * cell_w]
            hist = cv2.calcHist([cell], [0], None, [32], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            signature.extend(hist.tolist())
    return signature


def _face_match_score(ref_sig, live_sig):
    bins = 32
    n = len(ref_sig) // bins
    if n == 0 or len(ref_sig) != len(live_sig):
        return 0.0
    scores = []
    for i in range(n):
        s, e = i * bins, (i + 1) * bins
        ref = np.array(ref_sig[s:e], dtype=np.float32).reshape(-1, 1)
        live = np.array(live_sig[s:e], dtype=np.float32).reshape(-1, 1)
        scores.append(float(cv2.compareHist(ref, live, cv2.HISTCMP_CORREL)))
    return sum(scores) / len(scores)


def _liveness_score(frame_a, frame_b) -> float:
    faces_a, gray_a = _detect_faces(frame_a)
    faces_b, gray_b = _detect_faces(frame_b)
    if len(faces_a) >= 1 and len(faces_b) >= 1:
        xa, ya, wa, ha = max(faces_a, key=lambda f: f[2] * f[3])
        xb, yb, wb, hb = max(faces_b, key=lambda f: f[2] * f[3])
        face_a = cv2.resize(gray_a[ya : ya + ha, xa : xa + wa], (128, 128))
        face_b = cv2.resize(gray_b[yb : yb + hb, xb : xb + wb], (128, 128))
        return float(np.mean(cv2.absdiff(face_a, face_b)))
    return float(np.mean(cv2.absdiff(cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY))))


# ---------------------------------------------------------------------------
# Serializers (now work with dicts from Supabase)
# ---------------------------------------------------------------------------

def _student_to_dict(s):
    return {
        "id": s["id"], "roll_no": s["roll_no"], "full_name": s["full_name"],
        "department": s.get("department"), "semester": s.get("semester"),
        "face_enrolled": bool(s.get("face_signature")),
        "face_enrolled_at": s.get("face_enrolled_at"),
        "attendance_pct": _calc_attendance_pct(s["id"]),
        "has_login": s.get("user_id") is not None,
    }


def _session_to_dict(s):
    return {
        "id": s["id"], "name": s["session_name"],
        "starts_at": s["starts_at"], "expires_at": s["expires_at"],
        "is_active": s["is_active"],
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@main_bp.get("/")
@teacher_required
def dashboard():
    _deactivate_expired_sessions()
    students = supa.get_all_students()
    all_sessions = supa.get_recent_sessions(20)
    active_sessions = [s for s in all_sessions if s["is_active"]]
    recent_records = supa.get_recent_records(RECORDS_PER_PAGE)

    student_map = {s["id"]: s for s in students}
    session_map = {s["id"]: s for s in all_sessions}
    record_rows = []
    for r in recent_records:
        stu = student_map.get(r["student_id"])
        sess = session_map.get(r["session_id"])
        if not sess:
            sess = supa.get_session_by_id(r["session_id"])
        record_rows.append({
            "id": r["id"], "source": r["source"],
            "liveness_score": r["liveness_score"], "face_match_score": r["face_match_score"],
            "created_at": r["created_at"],
            "student_roll_no": stu["roll_no"] if stu else "-",
            "student_name": stu["full_name"] if stu else "-",
            "session_name": sess["session_name"] if sess else "-",
        })

    student_pcts = {s["id"]: _calc_attendance_pct(s["id"]) for s in students}
    total_closed = supa.count_closed_sessions()
    stats = {
        "students": len(students),
        "active_sessions": len(active_sessions),
        "attendance_records": supa.count_records(),
    }
    teachers = []
    if current_user.is_admin:
        teachers = supa.get_users_by_roles(["teacher", "admin"])

    return render_template("dashboard.html",
        stats=stats, students=students, student_pcts=student_pcts,
        total_closed=total_closed, sessions=all_sessions[:8],
        active_sessions=active_sessions, records=record_rows,
        teachers=teachers, cv_available=CV_AVAILABLE, user=current_user)


# ---------------------------------------------------------------------------
# Student Portal
# ---------------------------------------------------------------------------

@main_bp.get("/attend")
@student_required
def attend():
    student = supa.get_student_by_user_id(current_user.id)
    if not student:
        return render_template("attend.html", student=None, cv_available=CV_AVAILABLE,
                               user=current_user, attendance_pct=0, records=[])

    pct = _calc_attendance_pct(student["id"])
    recs = supa.get_records_for_student(student["id"], 10)
    records = []
    for r in recs:
        sess = supa.get_session_by_id(r["session_id"])
        records.append({
            "session_name": sess["session_name"] if sess else "-",
            "created_at": r["created_at"],
            "liveness_score": r["liveness_score"],
            "face_match_score": r["face_match_score"],
        })

    # Wrap student dict in a SimpleNamespace for template attribute access
    from types import SimpleNamespace
    student_obj = SimpleNamespace(**student)

    return render_template("attend.html", student=student_obj, cv_available=CV_AVAILABLE,
                           user=current_user, attendance_pct=pct, records=records)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@main_bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "smart-attendance-system", "cv_ready": CV_AVAILABLE})


# --- Teacher Management (Admin only) ---

@main_bp.post("/api/teachers")
@admin_required
def create_teacher():
    p = request.get_json(silent=True) or {}
    full_name = (p.get("full_name") or "").strip()
    email = (p.get("email") or "").strip().lower()
    password = p.get("password") or ""
    if not full_name or not email or not password:
        return jsonify({"ok": False, "message": "full_name, email, and password are required."}), 400
    if supa.get_user_by_email(email):
        return jsonify({"ok": False, "message": "A user with this email already exists."}), 409
    teacher = supa.create_user(email=email, password_hash=User.hash_password(password), role="teacher", full_name=full_name)
    return jsonify({"ok": True, "teacher": {"id": teacher["id"], "email": teacher["email"], "full_name": teacher["full_name"]}})


@main_bp.delete("/api/teachers/<int:user_id>")
@admin_required
def delete_teacher(user_id: int):
    user = supa.get_user_by_id(user_id)
    if not user or user["role"] != "teacher":
        return jsonify({"ok": False, "message": "Teacher not found."}), 404
    if user["id"] == current_user.id:
        return jsonify({"ok": False, "message": "Cannot delete yourself."}), 400
    supa.delete_user(user_id)
    return jsonify({"ok": True, "message": "Teacher deleted."})


# --- Student Management ---

@main_bp.post("/api/students")
@teacher_required
def create_student():
    p = request.get_json(silent=True) or {}
    roll_no = (p.get("roll_no") or "").strip().upper()
    full_name = (p.get("full_name") or "").strip()
    department = (p.get("department") or "").strip() or None
    semester = p.get("semester")
    email = (p.get("email") or "").strip().lower()
    password = p.get("password") or ""
    if not roll_no or not full_name:
        return jsonify({"ok": False, "message": "roll_no and full_name are required."}), 400
    if supa.get_student_by_roll_no(roll_no):
        return jsonify({"ok": False, "message": "Student with this roll number already exists."}), 409

    user_id = None
    if email and password:
        if supa.get_user_by_email(email):
            return jsonify({"ok": False, "message": "A user with this email already exists."}), 409
        user_row = supa.create_user(email=email, password_hash=User.hash_password(password), role="student", full_name=full_name)
        user_id = user_row["id"]

    student = supa.create_student({
        "roll_no": roll_no, "full_name": full_name, "department": department,
        "semester": int(semester) if str(semester or "").isdigit() else None,
        "user_id": user_id,
    })
    return jsonify({"ok": True, "student": _student_to_dict(student)})


@main_bp.delete("/api/students/<int:student_id>")
@teacher_required
def delete_student(student_id: int):
    student = supa.get_student_by_id(student_id)
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404
    supa.delete_records_for_student(student_id)
    linked_user_id = student.get("user_id")
    supa.delete_student_by_id(student_id)
    if linked_user_id:
        supa.delete_user(linked_user_id)
    return jsonify({"ok": True, "message": "Student deleted."})


@main_bp.post("/api/students/enroll-face")
@teacher_required
def enroll_student_face():
    p = request.get_json(silent=True) or {}
    roll_no = (p.get("roll_no") or "").strip().upper()
    frame_data = p.get("frame")
    if not roll_no or not frame_data:
        return jsonify({"ok": False, "message": "roll_no and frame are required."}), 400
    student = supa.get_student_by_roll_no(roll_no)
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404
    try:
        frame, _ = _decode_image_from_data_url(frame_data)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    face_roi = _primary_face_roi(frame)
    if face_roi is None:
        return jsonify({"ok": False, "message": "No clear face found."}), 400
    sig = _face_signature(face_roi)
    supa.update_student(student["id"], {
        "face_signature": json.dumps(sig, separators=(",", ":")),
        "face_enrolled_at": _now_utc().isoformat(),
    })
    student["face_signature"] = "enrolled"
    student["face_enrolled_at"] = _now_utc().isoformat()
    return jsonify({"ok": True, "message": "Face enrolled.", "student": _student_to_dict(student)})


# --- Sessions ---

@main_bp.post("/api/sessions")
@teacher_required
def create_session():
    p = request.get_json(silent=True) or {}
    session_name = (p.get("session_name") or "").strip()
    duration_min = int(p.get("duration_min") or 5)
    if not session_name:
        return jsonify({"ok": False, "message": "session_name is required."}), 400
    if duration_min < 1 or duration_min > 180:
        return jsonify({"ok": False, "message": "duration_min must be between 1 and 180."}), 400

    token = secrets.token_urlsafe(24)
    challenge = secrets.choice(ANTI_SPOOF_CHALLENGES)
    starts_at = _now_utc()
    expires_at = starts_at + timedelta(minutes=duration_min)

    session = supa.create_session({
        "teacher_id": current_user.id, "session_name": session_name,
        "qr_token": token, "anti_spoof_challenge": challenge,
        "starts_at": starts_at.isoformat(), "expires_at": expires_at.isoformat(),
        "is_active": True,
    })

    qr_payload = {"v": 1, "session_id": session["id"], "token": token,
                  "challenge": challenge, "expires_at": session["expires_at"]}
    qr_text = json.dumps(qr_payload, separators=(",", ":"))
    qr_image = _to_data_url_png(qr_text)

    return jsonify({"ok": True, "session": {**_session_to_dict(session), "challenge": challenge},
                    "qr_text": qr_text, "qr_image": qr_image})


@main_bp.post("/api/sessions/<int:session_id>/close")
@teacher_required
def close_session(session_id: int):
    session = supa.get_session_by_id(session_id)
    if not session:
        return jsonify({"ok": False, "message": "Session not found."}), 404
    if not session["is_active"]:
        return jsonify({"ok": False, "message": "Session already closed."}), 400
    supa.update_session(session_id, {"is_active": False})
    return jsonify({"ok": True, "message": "Session closed."})


@main_bp.get("/api/sessions/<int:session_id>/attendance")
@teacher_required
def get_session_attendance(session_id: int):
    session = supa.get_session_by_id(session_id)
    if not session:
        return jsonify({"ok": False, "message": "Session not found."}), 404
    students = supa.get_all_students()
    records = supa.get_records_for_session(session_id)
    record_map = {r["student_id"]: r for r in records}
    roster = []
    for s in students:
        rec = record_map.get(s["id"])
        roster.append({
            "student_id": s["id"], "roll_no": s["roll_no"], "full_name": s["full_name"],
            "department": s.get("department") or "Unknown", "semester": s.get("semester") or "-",
            "is_present": rec is not None, "source": rec["source"] if rec else None,
            "marked_at": rec["created_at"] if rec else None,
        })
    return jsonify({"ok": True, "session_name": session["session_name"], "is_active": session["is_active"],
                    "total_students": len(students), "present_count": len(records), "roster": roster})


@main_bp.post("/api/sessions/<int:session_id>/attendance/manual")
@teacher_required
def toggle_manual_attendance(session_id: int):
    session = supa.get_session_by_id(session_id)
    if not session:
        return jsonify({"ok": False, "message": "Session not found."}), 404
    p = request.get_json(silent=True) or {}
    student_id = p.get("student_id")
    status = p.get("status")
    if not student_id or status not in ("present", "absent"):
        return jsonify({"ok": False, "message": "student_id and valid status required."}), 400
    student = supa.get_student_by_id(student_id)
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404
    record = supa.get_record(session_id, student_id)
    if status == "present":
        if not record:
            supa.create_record({
                "session_id": session_id, "student_id": student_id, "status": "present",
                "source": "manual", "liveness_score": 100.0, "face_match_score": 1.0,
                "image_hash": f"manual_{secrets.token_hex(8)}",
            })
            msg = "Marked present manually."
        else:
            msg = "Already present."
    else:
        if record:
            supa.delete_record(record["id"])
            msg = "Marked absent."
        else:
            msg = "Already absent."
    return jsonify({"ok": True, "message": msg})


# --- Mark Attendance (Student) ---

@main_bp.post("/api/attendance/mark")
@student_required
def mark_attendance():
    p = request.get_json(silent=True) or {}
    qr_text = p.get("qr_text") or ""
    frame_a_data = p.get("frame_a")
    frame_b_data = p.get("frame_b")

    student = supa.get_student_by_user_id(current_user.id)
    if not student:
        return jsonify({"ok": False, "message": "No student profile linked."}), 400
    if not qr_text or not frame_a_data or not frame_b_data:
        return jsonify({"ok": False, "message": "qr_text, frame_a and frame_b are required."}), 400

    try:
        qr_payload = json.loads(qr_text)
    except Exception:
        return jsonify({"ok": False, "message": "Invalid QR content."}), 400

    session_id = qr_payload.get("session_id")
    token = qr_payload.get("token")
    if not session_id or not token:
        return jsonify({"ok": False, "message": "QR data missing session/token."}), 400

    session = supa.get_session_by_id(session_id)
    if not session:
        return jsonify({"ok": False, "message": "Session not found."}), 404
    if not session["is_active"] or _session_is_expired(session):
        supa.update_session(session_id, {"is_active": False})
        return jsonify({"ok": False, "message": "Session expired or closed."}), 400
    if token != session["qr_token"]:
        return jsonify({"ok": False, "message": "QR token mismatch."}), 400

    if supa.get_record(session["id"], student["id"]):
        return jsonify({"ok": False, "message": "Already marked for this session."}), 409

    try:
        frame_a, _ = _decode_image_from_data_url(frame_a_data)
        frame_b, frame_b_hash = _decode_image_from_data_url(frame_b_data)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    faces_a, _ = _detect_faces(frame_a)
    faces_b, _ = _detect_faces(frame_b)
    if len(faces_a) < 1 or len(faces_b) < 1:
        return jsonify({"ok": False, "message": "Face not detected in both frames."}), 400

    motion = _liveness_score(frame_a, frame_b)
    if motion < LIVENESS_THRESHOLD:
        return jsonify({"ok": False, "message": "Low liveness. Follow the challenge.", "liveness_score": motion}), 400

    if supa.get_record_by_hash(session["id"], frame_b_hash):
        return jsonify({"ok": False, "message": "Possible replay attack."}), 400

    if not student.get("face_signature"):
        return jsonify({"ok": False, "message": "Face not enrolled. Ask your teacher."}), 400

    live_face = _primary_face_roi(frame_b)
    if live_face is None:
        return jsonify({"ok": False, "message": "Live face not detected."}), 400

    try:
        ref_sig = json.loads(student["face_signature"])
    except Exception:
        return jsonify({"ok": False, "message": "Stored face invalid. Ask teacher to re-enroll."}), 400

    live_sig = _face_signature(live_face)
    match = _face_match_score(ref_sig, live_sig)
    if match < FACE_MATCH_THRESHOLD:
        return jsonify({"ok": False, "message": "Face mismatch.", "face_match_score": match}), 400

    record = supa.create_record({
        "session_id": session["id"], "student_id": student["id"], "status": "present",
        "source": "phone", "liveness_score": motion, "face_match_score": match,
        "image_hash": frame_b_hash,
    })
    return jsonify({"ok": True, "message": "Attendance marked successfully.", "record": {
        "id": record["id"], "student": student["roll_no"], "student_name": student["full_name"],
        "session": session["session_name"], "marked_at": record["created_at"],
        "liveness_score": motion, "face_match_score": match,
    }})


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@main_bp.get("/api/reports/attendance.csv")
@teacher_required
def export_attendance_report():
    _deactivate_expired_sessions()
    session_id = request.args.get("session_id", type=int)
    on_date = request.args.get("date")
    records = supa.get_records_filtered(session_id, on_date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["record_id", "marked_at_utc", "session_id", "session_name",
                      "student_roll_no", "student_name", "source", "status",
                      "liveness_score", "face_match_score"])

    for r in records:
        stu = supa.get_student_by_id(r["student_id"])
        sess = supa.get_session_by_id(r["session_id"])
        writer.writerow([
            r["id"], r["created_at"], sess["id"] if sess else "", sess["session_name"] if sess else "",
            stu["roll_no"] if stu else "", stu["full_name"] if stu else "",
            r["source"], r["status"],
            f"{r['liveness_score']:.4f}", f"{r['face_match_score']:.4f}",
        ])

    csv_content = output.getvalue()
    output.close()
    now_str = _now_utc().strftime("%Y%m%d_%H%M%S")
    return Response(csv_content, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=attendance_{now_str}.csv"})

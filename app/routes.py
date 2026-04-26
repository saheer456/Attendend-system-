import base64
import csv
import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta, timezone

import qrcode
from flask import Blueprint, Response, jsonify, render_template, request
from sqlalchemy import desc

from app import db
from app.models import AttendanceRecord, AttendanceSession, Student

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


def _now_utc():
    return datetime.now(timezone.utc)


def _as_naive_utc(dt):
    return dt.replace(tzinfo=None)


def _session_is_expired(session):
    return session.expires_at < _as_naive_utc(_now_utc())


def _deactivate_expired_sessions():
    active_sessions = AttendanceSession.query.filter_by(is_active=True).all()
    changed = False
    for session in active_sessions:
        if _session_is_expired(session):
            session.is_active = False
            changed = True
    if changed:
        db.session.commit()


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
        raise RuntimeError("OpenCV is unavailable. Install dependencies from requirements.txt.")
    nparr = np.frombuffer(raw, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image frame.")
    return frame, image_hash


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
    hist = cv2.calcHist([norm], [0], None, [64], [0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    return hist.tolist()


def _face_match_score(reference_signature, live_signature):
    ref = np.array(reference_signature, dtype=np.float32).reshape(-1, 1)
    live = np.array(live_signature, dtype=np.float32).reshape(-1, 1)
    return float(cv2.compareHist(ref, live, cv2.HISTCMP_CORREL))


def _liveness_score(frame_a, frame_b) -> float:
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
    delta = cv2.absdiff(gray_a, gray_b)
    return float(np.mean(delta))


def _student_to_dict(student):
    return {
        "id": student.id,
        "roll_no": student.roll_no,
        "full_name": student.full_name,
        "department": student.department,
        "semester": student.semester,
        "face_enrolled": bool(student.face_signature),
        "face_enrolled_at": (
            student.face_enrolled_at.isoformat() + "Z" if student.face_enrolled_at else None
        ),
    }


def _session_to_dict(session):
    return {
        "id": session.id,
        "name": session.session_name,
        "starts_at": session.starts_at.isoformat() + "Z",
        "expires_at": session.expires_at.isoformat() + "Z",
        "is_active": session.is_active,
    }


@main_bp.get("/")
def dashboard():
    _deactivate_expired_sessions()

    students = Student.query.order_by(Student.roll_no.asc()).all()
    all_sessions = AttendanceSession.query.order_by(desc(AttendanceSession.created_at)).all()
    active_sessions = [s for s in all_sessions if s.is_active]
    recent_records = AttendanceRecord.query.order_by(desc(AttendanceRecord.created_at)).limit(15).all()

    student_map = {s.id: s for s in students}
    session_map = {s.id: s for s in all_sessions}
    record_rows = []
    for record in recent_records:
        student = student_map.get(record.student_id)
        session = session_map.get(record.session_id)
        record_rows.append(
            {
                "id": record.id,
                "source": record.source,
                "liveness_score": record.liveness_score,
                "face_match_score": record.face_match_score,
                "created_at": record.created_at,
                "student_roll_no": student.roll_no if student else "-",
                "student_name": student.full_name if student else "-",
                "session_name": session.session_name if session else "-",
            }
        )

    stats = {
        "students": len(students),
        "active_sessions": len(active_sessions),
        "attendance_records": AttendanceRecord.query.count(),
    }

    return render_template(
        "dashboard.html",
        stats=stats,
        students=students,
        sessions=all_sessions[:8],
        active_sessions=active_sessions,
        records=record_rows,
        cv_available=CV_AVAILABLE,
    )


@main_bp.get("/health")
def health():
    _deactivate_expired_sessions()
    return jsonify({"status": "ok", "service": "smart-attendance-system", "cv_ready": CV_AVAILABLE})


@main_bp.get("/api/students")
def list_students():
    students = Student.query.order_by(Student.roll_no.asc()).all()
    return jsonify({"ok": True, "students": [_student_to_dict(s) for s in students]})


@main_bp.post("/api/students")
def create_student():
    payload = request.get_json(silent=True) or {}
    roll_no = (payload.get("roll_no") or "").strip().upper()
    full_name = (payload.get("full_name") or "").strip()
    department = (payload.get("department") or "").strip()
    semester = payload.get("semester")

    if not roll_no or not full_name:
        return jsonify({"ok": False, "message": "roll_no and full_name are required."}), 400

    if Student.query.filter_by(roll_no=roll_no).first():
        return jsonify({"ok": False, "message": "Student with this roll number already exists."}), 409

    student = Student(
        roll_no=roll_no,
        full_name=full_name,
        department=department or None,
        semester=int(semester) if str(semester).isdigit() else None,
    )
    db.session.add(student)
    db.session.commit()
    return jsonify({"ok": True, "student": _student_to_dict(student)})


@main_bp.delete("/api/students/<int:student_id>")
def delete_student(student_id: int):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404

    AttendanceRecord.query.filter_by(student_id=student_id).delete()
    db.session.delete(student)
    db.session.commit()
    return jsonify({"ok": True, "message": "Student deleted."})


@main_bp.post("/api/students/enroll-face")
def enroll_student_face():
    payload = request.get_json(silent=True) or {}
    roll_no = (payload.get("roll_no") or "").strip().upper()
    frame_data = payload.get("frame")

    if not roll_no or not frame_data:
        return jsonify({"ok": False, "message": "roll_no and frame are required."}), 400

    student = Student.query.filter_by(roll_no=roll_no).first()
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404

    try:
        frame, _ = _decode_image_from_data_url(frame_data)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    face_roi = _primary_face_roi(frame)
    if face_roi is None:
        return jsonify({"ok": False, "message": "No clear face found. Keep face centered and retry."}), 400

    signature = _face_signature(face_roi)
    student.face_signature = json.dumps(signature, separators=(",", ":"))
    student.face_enrolled_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "message": "Face enrolled.", "student": _student_to_dict(student)})


@main_bp.get("/api/sessions/active")
def list_active_sessions():
    _deactivate_expired_sessions()
    sessions = AttendanceSession.query.filter_by(is_active=True).order_by(desc(AttendanceSession.created_at)).all()
    return jsonify({"ok": True, "sessions": [_session_to_dict(s) for s in sessions]})


@main_bp.post("/api/sessions")
def create_session():
    payload = request.get_json(silent=True) or {}
    session_name = (payload.get("session_name") or "").strip()
    duration_min = int(payload.get("duration_min") or 5)

    if not session_name:
        return jsonify({"ok": False, "message": "session_name is required."}), 400
    if duration_min < 1 or duration_min > 60:
        return jsonify({"ok": False, "message": "duration_min must be between 1 and 60."}), 400

    token = secrets.token_urlsafe(24)
    challenge = secrets.choice(ANTI_SPOOF_CHALLENGES)
    starts_at = _as_naive_utc(_now_utc())
    expires_at = starts_at + timedelta(minutes=duration_min)

    session = AttendanceSession(
        session_name=session_name,
        qr_token=token,
        anti_spoof_challenge=challenge,
        starts_at=starts_at,
        expires_at=expires_at,
        is_active=True,
    )
    db.session.add(session)
    db.session.commit()

    qr_payload = {"v": 1, "session_id": session.id, "token": token, "expires_at": session.expires_at.isoformat() + "Z"}
    qr_text = json.dumps(qr_payload, separators=(",", ":"))
    qr_image = _to_data_url_png(qr_text)

    return jsonify(
        {
            "ok": True,
            "session": {**_session_to_dict(session), "challenge": session.anti_spoof_challenge},
            "qr_text": qr_text,
            "qr_image": qr_image,
        }
    )


@main_bp.post("/api/sessions/<int:session_id>/close")
def close_session(session_id: int):
    session = db.session.get(AttendanceSession, session_id)
    if not session:
        return jsonify({"ok": False, "message": "Session not found."}), 404
    if not session.is_active:
        return jsonify({"ok": False, "message": "Session already closed."}), 400

    session.is_active = False
    db.session.commit()
    return jsonify({"ok": True, "message": "Session closed."})


@main_bp.post("/api/attendance/mark")
def mark_attendance():
    payload = request.get_json(silent=True) or {}
    roll_no = (payload.get("roll_no") or "").strip().upper()
    qr_text = payload.get("qr_text") or ""
    frame_a_data = payload.get("frame_a")
    frame_b_data = payload.get("frame_b")
    source = (payload.get("source") or "webcam").strip().lower()
    source = source if source in {"webcam", "phone"} else "webcam"

    if not roll_no or not qr_text or not frame_a_data or not frame_b_data:
        return jsonify({"ok": False, "message": "roll_no, qr_text, frame_a and frame_b are required."}), 400

    student = Student.query.filter_by(roll_no=roll_no).first()
    if not student:
        return jsonify({"ok": False, "message": "Student not found."}), 404

    try:
        qr_payload = json.loads(qr_text)
    except Exception:
        return jsonify({"ok": False, "message": "Invalid QR content."}), 400

    session_id = qr_payload.get("session_id")
    token = qr_payload.get("token")
    if not session_id or not token:
        return jsonify({"ok": False, "message": "QR data missing session/token."}), 400

    session = db.session.get(AttendanceSession, session_id)
    if not session:
        return jsonify({"ok": False, "message": "Attendance session not found."}), 404
    if not session.is_active or _session_is_expired(session):
        session.is_active = False
        db.session.commit()
        return jsonify({"ok": False, "message": "Attendance session is expired or closed."}), 400
    if token != session.qr_token:
        return jsonify({"ok": False, "message": "QR token mismatch."}), 400

    if AttendanceRecord.query.filter_by(session_id=session.id, student_id=student.id).first():
        return jsonify({"ok": False, "message": "Attendance already marked for this student."}), 409

    try:
        frame_a, _ = _decode_image_from_data_url(frame_a_data)
        frame_b, frame_b_hash = _decode_image_from_data_url(frame_b_data)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    faces_a, _ = _detect_faces(frame_a)
    faces_b, _ = _detect_faces(frame_b)
    if len(faces_a) < 1 or len(faces_b) < 1:
        return jsonify({"ok": False, "message": "Face not detected clearly in both frames."}), 400

    motion_score = _liveness_score(frame_a, frame_b)
    if motion_score < LIVENESS_THRESHOLD:
        return jsonify(
            {
                "ok": False,
                "message": "Low live motion detected. Blink/turn head and try again.",
                "liveness_score": motion_score,
            }
        ), 400

    replay = AttendanceRecord.query.filter_by(session_id=session.id, image_hash=frame_b_hash).first()
    if replay:
        return jsonify({"ok": False, "message": "Possible replay attack detected."}), 400

    if not student.face_signature:
        return jsonify({"ok": False, "message": "Student face is not enrolled yet. Enroll face first."}), 400

    live_face = _primary_face_roi(frame_b)
    if live_face is None:
        return jsonify({"ok": False, "message": "Live face not detected for identity confirmation."}), 400

    try:
        reference_signature = json.loads(student.face_signature)
    except Exception:
        return jsonify({"ok": False, "message": "Stored face profile is invalid. Re-enroll the student."}), 400

    live_signature = _face_signature(live_face)
    match_score = _face_match_score(reference_signature, live_signature)
    if match_score < FACE_MATCH_THRESHOLD:
        return jsonify(
            {
                "ok": False,
                "message": "Face mismatch. Attendance blocked for identity safety.",
                "face_match_score": match_score,
            }
        ), 400

    record = AttendanceRecord(
        session_id=session.id,
        student_id=student.id,
        status="present",
        source=source,
        liveness_score=motion_score,
        face_match_score=match_score,
        image_hash=frame_b_hash,
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "message": "Attendance marked successfully.",
            "record": {
                "id": record.id,
                "student": student.roll_no,
                "student_name": student.full_name,
                "session": session.session_name,
                "marked_at": record.created_at.isoformat() + "Z",
                "liveness_score": motion_score,
                "face_match_score": match_score,
            },
        }
    )


@main_bp.get("/api/reports/attendance.csv")
def export_attendance_report():
    _deactivate_expired_sessions()
    session_id = request.args.get("session_id", type=int)
    on_date = request.args.get("date")

    rows = (
        db.session.query(AttendanceRecord, Student, AttendanceSession)
        .join(Student, AttendanceRecord.student_id == Student.id)
        .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
        .order_by(desc(AttendanceRecord.created_at))
    )
    if session_id:
        rows = rows.filter(AttendanceRecord.session_id == session_id)
    if on_date:
        rows = rows.filter(db.func.date(AttendanceRecord.created_at) == on_date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "record_id",
            "marked_at_utc",
            "session_id",
            "session_name",
            "student_roll_no",
            "student_name",
            "source",
            "status",
            "liveness_score",
            "face_match_score",
        ]
    )

    for record, student, session in rows.all():
        writer.writerow(
            [
                record.id,
                record.created_at.isoformat() + "Z",
                session.id,
                session.session_name,
                student.roll_no,
                student.full_name,
                record.source,
                record.status,
                f"{record.liveness_score:.4f}",
                f"{record.face_match_score:.4f}",
            ]
        )

    csv_content = output.getvalue()
    output.close()
    filename = f"attendance_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

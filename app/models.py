from datetime import datetime

from app import db


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    semester = db.Column(db.Integer, nullable=True)
    face_signature = db.Column(db.Text, nullable=True)
    face_enrolled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AttendanceSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(120), nullable=False)
    qr_token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    anti_spoof_challenge = db.Column(db.String(160), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_session.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    status = db.Column(db.String(20), default="present", nullable=False)
    source = db.Column(db.String(20), nullable=False)  # webcam | phone
    liveness_score = db.Column(db.Float, nullable=False)
    face_match_score = db.Column(db.Float, nullable=False)
    image_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )

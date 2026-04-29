-- ===================================================================
-- Smart Attendance System — Supabase Table Creation
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- ===================================================================

-- 1. Users table (admin, teacher, student logins)
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    full_name   TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 2. Students table
CREATE TABLE IF NOT EXISTS students (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    roll_no         TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL,
    department      TEXT,
    semester        INTEGER,
    face_signature  TEXT,
    face_enrolled_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 3. Attendance Sessions table
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id                   BIGSERIAL PRIMARY KEY,
    teacher_id           BIGINT REFERENCES users(id) ON DELETE SET NULL,
    session_name         TEXT NOT NULL,
    qr_token             TEXT UNIQUE NOT NULL,
    anti_spoof_challenge TEXT NOT NULL,
    starts_at            TIMESTAMPTZ NOT NULL,
    expires_at           TIMESTAMPTZ NOT NULL,
    is_active            BOOLEAN DEFAULT true NOT NULL,
    created_at           TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 4. Attendance Records table
CREATE TABLE IF NOT EXISTS attendance_records (
    id               BIGSERIAL PRIMARY KEY,
    session_id       BIGINT NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id       BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status           TEXT DEFAULT 'present' NOT NULL,
    source           TEXT NOT NULL,
    liveness_score   DOUBLE PRECISION NOT NULL,
    face_match_score DOUBLE PRECISION NOT NULL,
    image_hash       TEXT NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT now() NOT NULL,
    UNIQUE (session_id, student_id)
);

-- 5. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_students_roll_no ON students(roll_no);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_active ON attendance_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_attendance_records_session ON attendance_records(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_records_student ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_records_hash ON attendance_records(image_hash);

-- 6. Insert default admin account (password: "admin")
-- The hash below is for the password "admin" using werkzeug's pbkdf2:sha256
-- It will be inserted by the application on startup if it doesn't exist.

# Smart Attendance System

Flask web app for attendance using:
- Student database
- Live QR session generation
- Phone camera / webcam capture
- Anti-fake attendance checks

No login/logout flow is used.

## Features

- Single dashboard for full workflow
- Add students to database
- Delete students from dashboard
- Enroll face profile per student
- Generate time-limited QR attendance sessions
- Close active sessions manually
- Scan QR using browser camera
- Mark attendance with two live camera frames
- Export attendance CSV report (all sessions / one session / by date)
- Anti-fake mechanism:
  - QR token validation
  - Session expiry enforcement
  - Duplicate student mark blocking
  - Face detection on both frames
  - Live motion (liveness) check
  - Live face vs enrolled student face match check
  - Replay image hash blocking per session

## Quick Start

1. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

2. Run app:

```powershell
python run.py
```

3. Open:

`http://127.0.0.1:5000`

## Use Supabase as Database

1. Copy `.env.example` to `.env`.
2. Set `DATABASE_URL` to your Supabase Postgres connection string.
3. Keep `DB_SSLMODE=require`.
4. Restart app.

Example format:

```env
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
DB_SSLMODE=require
```

The app will automatically:
- accept `postgres://` and convert it
- enforce SSL mode for Postgres connections
- keep SQLite fallback for local development

## API Endpoints

- `POST /api/students` - add student
- `GET /api/students` - list students
- `DELETE /api/students/<student_id>` - delete student
- `POST /api/students/enroll-face` - enroll or update student face profile
- `POST /api/sessions` - create QR attendance session
- `GET /api/sessions/active` - list active sessions
- `POST /api/sessions/<session_id>/close` - close session
- `POST /api/attendance/mark` - mark attendance with QR + camera frames
- `GET /api/reports/attendance.csv` - export report (supports `session_id` and `date`)
- `GET /health` - service and OpenCV readiness

## Project Structure

```text
app/
  __init__.py
  models.py
  routes.py
  templates/
    base.html
    dashboard.html
  static/
    css/styles.css
    js/app.js
run.py
requirements.txt
TASK_BOARD.md
```

# Smart Attendance System

A Flask-based attendance management system using QR code sessions and real-time face verification. Designed for classrooms where a **teacher** controls sessions from a dashboard and **students** mark attendance from their phones.

## How It Works

The system has two separate interfaces:

| Interface | URL | Who uses it | Purpose |
|---|---|---|---|
| **Admin Dashboard** | `http://127.0.0.1:5000/` | Teacher / Admin | Manage students, create QR sessions, view reports |
| **Student Portal** | `http://127.0.0.1:5000/attend` | Students | Scan QR, verify face, mark attendance |

### Attendance Flow

```
Teacher creates session → QR displayed on screen → Student scans QR on phone
→ Student captures face → System verifies identity → Attendance marked
```

---

## Quick Start

### 1. Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### 2. Set Up Environment

Copy `.env.example` to `.env` and configure your database:

```env
# For Supabase (recommended):
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
DB_SSLMODE=require
SECRET_KEY=your-secret-key-here

# For local development (no config needed, uses SQLite automatically)
```

### 3. Run the App

```powershell
python run.py
```

### 4. Open the Dashboard

Open `http://127.0.0.1:5000` in your browser.

---

## Usage Guide

### Default Admin Login

The system automatically creates a default admin account on startup:
- **Email**: `admin@college.edu`
- **Password**: `admin`

*(Note: Change this password after logging in for production use.)*

### Step 1: Create Teacher Accounts (Admin only)

1. Log in with the admin account at `http://127.0.0.1:5000`.
2. Click **Teachers** in the sidebar.
3. Add new teacher accounts.
4. Log out and let teachers log in with their new accounts to manage students.

### Step 2: Register Students (Teacher Dashboard)

1. Log in as a Teacher.
2. Click **Students** in the sidebar.
3. Fill in the student details, including their **Student Email** and **Password** so they can log in to the student portal.
4. Click **Add Student**.

### Step 2: Enroll Student Faces (Admin Dashboard)

1. On the **Students** tab, use the **Enroll Face** section.
2. Select a student from the dropdown.
3. Click **Start Camera** and position the student's face clearly in view.
4. Click **Capture & Enroll Face**.
5. The student's face profile is now stored for future verification.

### Step 3: Create an Attendance Session (Admin Dashboard)

1. Click **Sessions** in the sidebar.
2. Enter a session name (e.g., "MCA S3 — DBMS Hour 1").
3. Set the duration (1–180 minutes).
4. Click **Generate QR Session**.
5. A QR code will appear — **display this on the classroom projector or screen**.

### Step 4: Students Mark Attendance (Student Portal)

1. Students open `http://127.0.0.1:5000/attend` on their **phones**.
2. **Step 1 — Identity**: Select their roll number. The system checks if their face is enrolled.
3. **Step 2 — Scan QR**: Point the phone camera at the teacher's QR code on the projector.
4. **Step 3 — Face Verify**: The phone's front camera captures two frames with a short delay. The system checks:
   - **Liveness**: Did the student actually move (not a photo)?
   - **Face Match**: Does the live face match the enrolled profile?
5. If both checks pass, attendance is marked as **present**.

### Step 5: View Reports (Admin Dashboard)

1. Click **Records & Reports** in the sidebar.
2. Filter by session or date.
3. Click **Download CSV** to export the attendance report.

---

## Anti-Fraud Mechanisms

| Mechanism | What it prevents |
|---|---|
| **QR Token Validation** | Only the active session's QR code is accepted |
| **Session Expiry** | QR codes stop working after the set duration |
| **Duplicate Check** | A student can only mark attendance once per session |
| **Face Detection** | Both captured frames must contain a detectable face |
| **Liveness Score** | Compares two frames for real movement (rejects static photos) |
| **Multi-Region Face Match** | Splits the face into a 4×4 grid for spatial feature comparison |
| **Replay Hash Check** | Rejects identical images reused from a previous submission |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Admin Dashboard |
| `GET` | `/attend` | Student Attendance Portal |
| `GET` | `/health` | Service health check |
| `GET` | `/api/students` | List all students |
| `POST` | `/api/students` | Register a student |
| `DELETE` | `/api/students/<id>` | Delete a student |
| `POST` | `/api/students/enroll-face` | Enroll or update face profile |
| `GET` | `/api/sessions/active` | List active sessions |
| `POST` | `/api/sessions` | Create a new QR session |
| `POST` | `/api/sessions/<id>/close` | Close a session manually |
| `POST` | `/api/attendance/mark` | Mark attendance (QR + face) |
| `GET` | `/api/reports/attendance.csv` | Export CSV (supports `session_id`, `date` filters) |

---

## Using Supabase as Database

1. Copy `.env.example` to `.env`.
2. Set `DATABASE_URL` to your Supabase Postgres connection string.
3. Set `DB_SSLMODE=require`.
4. Restart the app.

The app automatically handles:
- Converting `postgres://` URLs to `postgresql+psycopg://`
- Enforcing SSL for Postgres connections
- Connection pooling with `pool_size=5` and `max_overflow=10`
- Falling back to SQLite for local development when no `DATABASE_URL` is set

---

## Project Structure

```
├── run.py                          # App entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── app/
│   ├── __init__.py                 # App factory, DB config
│   ├── models.py                   # SQLAlchemy models
│   ├── routes.py                   # API & page routes
│   ├── templates/
│   │   ├── base.html               # Base HTML template
│   │   ├── dashboard.html          # Admin dashboard (sidebar + tabs)
│   │   └── attend.html             # Student attendance portal
│   └── static/
│       ├── css/styles.css          # Design system
│       └── js/
│           ├── app.js              # Admin dashboard logic
│           └── attend.js           # Student portal logic
```

---

## Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-Migrate
- **Database**: Supabase (PostgreSQL) or SQLite (local dev)
- **Face Detection**: OpenCV (Haar Cascades)
- **Face Matching**: Multi-region histogram correlation
- **QR Generation**: `qrcode` + `Pillow`
- **QR Scanning**: `html5-qrcode` (browser-based)
- **Frontend**: Vanilla HTML/CSS/JS (no framework dependencies)

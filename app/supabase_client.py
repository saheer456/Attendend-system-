"""
Supabase REST API client for the Smart Attendance System.
Replaces SQLAlchemy with direct HTTP calls to the PostgREST API.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_BASE = f"{SUPABASE_URL}/rest/v1"
_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _url(table: str) -> str:
    return f"{_BASE}/{table}"


def _get(table: str, params: dict | None = None) -> list[dict]:
    """SELECT rows from a table."""
    resp = requests.get(_url(table), headers=_HEADERS, params=params or {})
    resp.raise_for_status()
    return resp.json()


def _get_one(table: str, params: dict | None = None) -> dict | None:
    """SELECT single row. Returns None if not found."""
    p = dict(params or {})
    p["limit"] = 1
    rows = _get(table, p)
    return rows[0] if rows else None


def _insert(table: str, data: dict) -> dict:
    """INSERT a row and return the created record."""
    resp = requests.post(_url(table), headers=_HEADERS, json=data)
    resp.raise_for_status()
    result = resp.json()
    return result[0] if isinstance(result, list) else result


def _update(table: str, params: dict, data: dict) -> list[dict]:
    """UPDATE rows matching params."""
    resp = requests.patch(_url(table), headers=_HEADERS, params=params, json=data)
    resp.raise_for_status()
    return resp.json()


def _delete(table: str, params: dict) -> None:
    """DELETE rows matching params."""
    resp = requests.delete(_url(table), headers=_HEADERS, params=params)
    resp.raise_for_status()


def _count(table: str, params: dict | None = None) -> int:
    """COUNT rows matching filter."""
    h = {**_HEADERS, "Prefer": "count=exact", "Range-Unit": "items"}
    h.pop("Content-Type", None)
    p = dict(params or {})
    p["select"] = "id"
    resp = requests.get(_url(table), headers=h, params=p)
    resp.raise_for_status()
    # The count is in the Content-Range header: "0-N/total"
    cr = resp.headers.get("Content-Range", "")
    if "/" in cr:
        total = cr.split("/")[1]
        return int(total) if total != "*" else 0
    return len(resp.json())


# ===================================================================
# Table-specific helpers
# ===================================================================

# --- Users ---

def get_user_by_id(user_id: int) -> dict | None:
    return _get_one("users", {"id": f"eq.{user_id}"})


def get_user_by_email(email: str) -> dict | None:
    return _get_one("users", {"email": f"eq.{email}"})


def create_user(email: str, password_hash: str, role: str, full_name: str) -> dict:
    return _insert("users", {
        "email": email,
        "password_hash": password_hash,
        "role": role,
        "full_name": full_name,
    })


def delete_user(user_id: int) -> None:
    _delete("users", {"id": f"eq.{user_id}"})


def get_users_by_roles(roles: list[str]) -> list[dict]:
    role_filter = ",".join(roles)
    return _get("users", {"role": f"in.({role_filter})", "order": "created_at.desc"})


def count_users() -> int:
    return _count("users")


# --- Students ---

def get_student_by_id(student_id: int) -> dict | None:
    return _get_one("students", {"id": f"eq.{student_id}"})


def get_student_by_roll_no(roll_no: str) -> dict | None:
    return _get_one("students", {"roll_no": f"eq.{roll_no}"})


def get_student_by_user_id(user_id: int) -> dict | None:
    return _get_one("students", {"user_id": f"eq.{user_id}"})


def get_all_students() -> list[dict]:
    return _get("students", {"order": "roll_no.asc"})


def create_student(data: dict) -> dict:
    return _insert("students", data)


def update_student(student_id: int, data: dict) -> list[dict]:
    return _update("students", {"id": f"eq.{student_id}"}, data)


def delete_student_by_id(student_id: int) -> None:
    _delete("students", {"id": f"eq.{student_id}"})


# --- Attendance Sessions ---

def get_session_by_id(session_id: int) -> dict | None:
    return _get_one("attendance_sessions", {"id": f"eq.{session_id}"})


def get_active_sessions() -> list[dict]:
    return _get("attendance_sessions", {
        "is_active": "eq.true",
        "order": "created_at.desc",
    })


def get_recent_sessions(limit: int = 20) -> list[dict]:
    return _get("attendance_sessions", {
        "order": "created_at.desc",
        "limit": limit,
    })


def create_session(data: dict) -> dict:
    return _insert("attendance_sessions", data)


def update_session(session_id: int, data: dict) -> list[dict]:
    return _update("attendance_sessions", {"id": f"eq.{session_id}"}, data)


def count_closed_sessions() -> int:
    return _count("attendance_sessions", {"is_active": "eq.false"})


# --- Attendance Records ---

def get_record(session_id: int, student_id: int) -> dict | None:
    return _get_one("attendance_records", {
        "session_id": f"eq.{session_id}",
        "student_id": f"eq.{student_id}",
    })


def get_record_by_hash(session_id: int, image_hash: str) -> dict | None:
    return _get_one("attendance_records", {
        "session_id": f"eq.{session_id}",
        "image_hash": f"eq.{image_hash}",
    })


def get_records_for_session(session_id: int) -> list[dict]:
    return _get("attendance_records", {"session_id": f"eq.{session_id}"})


def get_records_for_student(student_id: int, limit: int = 10) -> list[dict]:
    return _get("attendance_records", {
        "student_id": f"eq.{student_id}",
        "order": "created_at.desc",
        "limit": limit,
    })


def get_recent_records(limit: int = 15) -> list[dict]:
    return _get("attendance_records", {
        "order": "created_at.desc",
        "limit": limit,
    })


def create_record(data: dict) -> dict:
    return _insert("attendance_records", data)


def delete_record(record_id: int) -> None:
    _delete("attendance_records", {"id": f"eq.{record_id}"})


def delete_records_for_student(student_id: int) -> None:
    _delete("attendance_records", {"student_id": f"eq.{student_id}"})


def count_records() -> int:
    return _count("attendance_records")


def count_records_for_student(student_id: int) -> int:
    return _count("attendance_records", {"student_id": f"eq.{student_id}"})


def get_records_filtered(session_id: int | None = None, on_date: str | None = None) -> list[dict]:
    """Get attendance records with optional session and date filters."""
    params = {"order": "created_at.desc"}
    if session_id:
        params["session_id"] = f"eq.{session_id}"
    if on_date:
        params["created_at"] = f"gte.{on_date}T00:00:00"
        # PostgREST doesn't have a simple date() filter, so we filter a range
        # We'll add an end-of-day filter too
        params["created_at"] = f"gte.{on_date}T00:00:00"
    return _get("attendance_records", params)

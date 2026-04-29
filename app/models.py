"""
User model wrapper for Flask-Login compatibility.
Data is stored in Supabase, this class wraps a dict to provide
the interface Flask-Login expects.
"""

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


class User(UserMixin):
    """Wraps a Supabase user row dict for Flask-Login."""

    def __init__(self, row: dict):
        self._row = row
        self.id = row.get("id")
        self.email = row.get("email", "")
        self.password_hash = row.get("password_hash", "")
        self.role = row.get("role", "")
        self.full_name = row.get("full_name", "")
        self.created_at = row.get("created_at", "")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_teacher(self):
        return self.role in ("admin", "teacher")

    @property
    def is_student(self):
        return self.role == "student"

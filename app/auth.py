from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.models import User
from app import supabase_client as supa

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    # If no users exist at all, redirect to setup
    if supa.count_users() == 0:
        return redirect(url_for("auth.setup"))

    return render_template("login.html")


@auth_bp.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("auth.login"))

    row = supa.get_user_by_email(email)
    if not row:
        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    user = User(row)
    if not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)
    next_page = request.args.get("next")
    if next_page:
        return redirect(next_page)
    return _redirect_by_role(user)


@auth_bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.get("/setup")
def setup():
    # Only allow if no users exist (first-run)
    if supa.count_users() > 0:
        return redirect(url_for("auth.login"))
    return render_template("setup.html")


@auth_bp.post("/setup")
def setup_post():
    if supa.count_users() > 0:
        flash("Setup already completed.", "error")
        return redirect(url_for("auth.login"))

    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not full_name or not email or not password:
        flash("All fields are required.", "error")
        return redirect(url_for("auth.setup"))

    if len(password) < 4:
        flash("Password must be at least 4 characters.", "error")
        return redirect(url_for("auth.setup"))

    row = supa.create_user(
        email=email,
        password_hash=User.hash_password(password),
        role="admin",
        full_name=full_name,
    )
    admin = User(row)
    login_user(admin)
    return redirect(url_for("main.dashboard"))


def _redirect_by_role(user):
    if user.is_student:
        return redirect(url_for("main.attend"))
    return redirect(url_for("main.dashboard"))

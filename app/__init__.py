import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import inspect, text

db = SQLAlchemy()
migrate = Migrate()

load_dotenv()


def _normalize_database_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return "sqlite:///attendance.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _build_sqlalchemy_settings():
    database_url = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///attendance.db"))
    engine_options = {"pool_pre_ping": True}

    if database_url.startswith("postgresql"):
        engine_options["pool_recycle"] = 1800
        engine_options["connect_args"] = {"sslmode": os.getenv("DB_SSLMODE", "require")}

    return database_url, engine_options


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    database_url, engine_options = _build_sqlalchemy_settings()

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-this"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options,
        SUPABASE_URL=os.getenv("SUPABASE_URL", "").strip(),
        SUPABASE_ANON_KEY=os.getenv("SUPABASE_ANON_KEY", "").strip(),
        SUPABASE_SERVICE_ROLE_KEY=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
    )

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from app import models
        db.create_all()
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            _ensure_lightweight_schema_updates()

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app


def _ensure_lightweight_schema_updates():
    """
    Dev-friendly schema compatibility for SQLite when migrations are not run yet.
    """
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    if "student" in tables:
        columns = {c["name"] for c in inspector.get_columns("student")}
        with db.engine.begin() as conn:
            if "face_signature" not in columns:
                conn.execute(text("ALTER TABLE student ADD COLUMN face_signature TEXT"))
            if "face_enrolled_at" not in columns:
                conn.execute(text("ALTER TABLE student ADD COLUMN face_enrolled_at DATETIME"))

    if "attendance_record" in tables:
        columns = {c["name"] for c in inspector.get_columns("attendance_record")}
        with db.engine.begin() as conn:
            if "face_match_score" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE attendance_record "
                        "ADD COLUMN face_match_score FLOAT DEFAULT 0 NOT NULL"
                    )
                )

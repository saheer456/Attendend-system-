import os

from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv

login_manager = LoginManager()

load_dotenv()


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-this"),
    )

    # Flask-Login
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        from app.supabase_client import get_user_by_id
        row = get_user_by_id(int(user_id))
        if row:
            return User(row)
        return None

    # Seed default admin on first request (if not exists)
    @app.before_request
    def _ensure_admin():
        app.before_request_funcs[None].remove(_ensure_admin)  # run only once
        from app.models import User as UserModel
        from app.supabase_client import get_user_by_email, create_user
        try:
            if not get_user_by_email("admin@college.edu"):
                create_user(
                    email="admin@college.edu",
                    password_hash=UserModel.hash_password("admin"),
                    role="admin",
                    full_name="Admin",
                )
                print("[INIT] Default admin account created: admin@college.edu / admin")
        except Exception as e:
            print(f"[INIT] Could not seed admin (tables may not exist yet): {e}")

    # Register blueprints
    from app.auth import auth_bp
    from app.routes import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app

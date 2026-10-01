import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///emp.db")
    # The admin account is created automatically on first start.
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@emp.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    # Emails are only really sent when MAIL_SERVER is set; otherwise they are just logged.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "8025"))
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_SENDER", "emp@emp.local")
    MAIL_SUPPRESS_SEND = "MAIL_SERVER" not in os.environ


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True

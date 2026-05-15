import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-in-production")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    PLATFORM_FEE_PERCENT = float(os.environ.get("PLATFORM_FEE_PERCENT", "7.0"))
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///indies_dev.db"
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")
    # Railway returns postgres:// but SQLAlchemy needs postgresql://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )

    @classmethod
    def validate(cls):
        errors = []
        if cls.SECRET_KEY in ("dev-secret-change-in-production", ""):
            errors.append("SECRET_KEY must be set to a random string in production")
        if cls.JWT_SECRET_KEY in ("jwt-secret-change-in-production", ""):
            errors.append("JWT_SECRET_KEY must be set to a random string in production")
        if not cls.STRIPE_SECRET_KEY:
            errors.append("STRIPE_SECRET_KEY is not set")
        if not cls.SQLALCHEMY_DATABASE_URI:
            errors.append("DATABASE_URL is not set")
        if errors:
            raise RuntimeError("Production config errors:\n" + "\n".join(f"  - {e}" for e in errors))


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}

from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in {"true", "1", "yes"}

@dataclass
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    public_origin: str = field(default_factory=lambda: os.getenv("PUBLIC_ORIGIN", "http://127.0.0.1:8000"))
    cookie_secure: bool = field(default_factory=lambda: flag("SESSION_COOKIE_SECURE", os.getenv("APP_ENV") == "production"))
    remember_hours: int = 720
    database_url: str = field(repr=False, default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/milaan.db"))
    migration_database_url: str = field(repr=False, default_factory=lambda: os.getenv("MIGRATION_DATABASE_URL", ""))
    database_pool_size: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "5")))
    database_max_overflow: int = field(default_factory=lambda: int(os.getenv("DATABASE_MAX_OVERFLOW", "0")))
    storage_backend: str = field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "local"))
    s3_endpoint_url: str = field(default_factory=lambda: os.getenv("S3_ENDPOINT_URL", ""))
    s3_bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))
    s3_region: str = field(default_factory=lambda: os.getenv("S3_REGION", ""))
    s3_access_key_id: str = field(repr=False, default_factory=lambda: os.getenv("S3_ACCESS_KEY_ID", ""))
    s3_secret_access_key: str = field(repr=False, default_factory=lambda: os.getenv("S3_SECRET_ACCESS_KEY", ""))
    s3_session_token: str = field(repr=False, default_factory=lambda: os.getenv("S3_SESSION_TOKEN", ""))
    s3_prefix: str = field(default_factory=lambda: os.getenv("S3_PREFIX", "receipts/v1/"))
    s3_addressing_style: str = field(default_factory=lambda: os.getenv("S3_ADDRESSING_STYLE", "path"))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", "./data/uploads")))
    cors_origins: list[str] = field(default_factory=lambda: [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://localhost:8080,http://127.0.0.1:8080").split(",") if x.strip()])
    run_worker: bool = field(default_factory=lambda: flag("RUN_WORKER_IN_API", True))
    registration_open: bool = field(default_factory=lambda: flag("ALLOW_REGISTRATION", os.getenv("APP_ENV") != "production"))
    enable_demo: bool = field(default_factory=lambda: flag("ENABLE_DEMO", True))
    session_hours: int = field(default_factory=lambda: int(os.getenv("SESSION_HOURS", "12")))
    retention_hours: int = field(default_factory=lambda: int(os.getenv("BATCH_RETENTION_HOURS", "168")))
    extraction_provider: str = field(default_factory=lambda: os.getenv("EXTRACTION_PROVIDER", "manual"))
    gemini_key: str = field(repr=False, default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", ""))
    require_email_verification: bool = field(default_factory=lambda: flag("REQUIRE_EMAIL_VERIFICATION", True))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(repr=False, default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))
    smtp_security: str = field(default_factory=lambda: os.getenv("SMTP_SECURITY", "starttls"))
    model_timeout: int = 25
    worker_lease_seconds: int = 300
    max_batches: int = 100
    max_claims: int = 100
    max_rows: int = 2000
    max_image_bytes: int = 10 * 1024 * 1024
    max_request_bytes: int = 12 * 1024 * 1024
    # Demo seller account – auto-created on startup when DEMO_SELLER_EMAIL is set.
    demo_seller_email: str = field(default_factory=lambda: os.getenv("DEMO_SELLER_EMAIL", ""))
    demo_seller_password: str = field(repr=False, default_factory=lambda: os.getenv("DEMO_SELLER_PASSWORD", ""))
    demo_account_id: str = field(default_factory=lambda: os.getenv("DEMO_ACCOUNT_ID", "milaan-main"))
    testing: bool = False

    @property
    def cookie_name(self):
        return "__Host-milaan_session" if self.cookie_secure else "milaan_session"

    def __post_init__(self):
        from urllib.parse import urlparse
        from .database import database_url
        runtime = database_url(self.database_url)
        if not 1 <= self.database_pool_size <= 20 or not 0 <= self.database_max_overflow <= 20:
            raise ValueError("Database pool limits must be bounded (size 1–20, overflow 0–20)")
        if self.migration_database_url:
            migration = database_url(self.migration_database_url)
            if migration.get_backend_name() != runtime.get_backend_name():
                raise ValueError("Runtime and migration database dialects must match")
            if migration.host and "-pooler." in migration.host:
                raise ValueError("MIGRATION_DATABASE_URL must use the direct endpoint")
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be local or s3")
        if self.storage_backend == "s3":
            endpoint = urlparse(self.s3_endpoint_url)
            if (endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password
                    or endpoint.query or endpoint.fragment):
                raise ValueError("Set a valid S3_ENDPOINT_URL without credentials or query")
            if not all([self.s3_bucket, self.s3_region, self.s3_access_key_id, self.s3_secret_access_key]):
                raise ValueError("S3 storage requires bucket, region and explicit credentials")
            import re
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9/_-]{0,150}/", self.s3_prefix) or "//" in self.s3_prefix:
                raise ValueError("S3_PREFIX must be a dedicated nonempty namespace ending in /")
            if self.s3_addressing_style not in {"path", "virtual"}:
                raise ValueError("S3_ADDRESSING_STYLE must be path or virtual")
            if self.app_env == "production" and endpoint.scheme != "https":
                raise ValueError("Production S3 requires HTTPS")
        if self.app_env == "production":
            if runtime.get_backend_name() != "postgresql" or self.storage_backend != "s3":
                raise ValueError("Production requires PostgreSQL and private S3 storage; local storage is development-only")
            for target in [runtime] + ([database_url(self.migration_database_url)] if self.migration_database_url else []):
                if target.query.get("sslmode") not in {"verify-full", "verify-ca"}:
                    raise ValueError("Production PostgreSQL requires sslmode=verify-full (or verify-ca)")
        origin = urlparse(self.public_origin)
        if origin.scheme not in {"http", "https"} or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in {"", "/"}:
            raise ValueError("PUBLIC_ORIGIN must be an HTTP(S) origin without credentials, path or query")
        self.public_origin = self.public_origin.rstrip("/")
        if self.app_env not in {"development", "production"}:
            raise ValueError("APP_ENV must be development or production")
        if self.app_env == "production" and (not self.cookie_secure or origin.scheme != "https" or not self.require_email_verification):
            raise ValueError("Production requires HTTPS PUBLIC_ORIGIN, secure cookies and email verification")
        if self.app_env == "production" and (self.demo_seller_email or self.demo_seller_password):
            raise ValueError("Demo operator provisioning is development-only")
        if self.smtp_security not in {"starttls", "ssl"}:
            raise ValueError("SMTP_SECURITY must be starttls or ssl")
        if self.extraction_provider not in {"manual", "gemini"}:
            raise ValueError("EXTRACTION_PROVIDER must be manual or gemini")
        if "*" in self.cors_origins:
            raise ValueError("Set explicit CORS_ORIGINS, not '*'")
        if not 1 <= self.retention_hours <= 8760:
            raise ValueError("BATCH_RETENTION_HOURS must be between 1 and 8760")

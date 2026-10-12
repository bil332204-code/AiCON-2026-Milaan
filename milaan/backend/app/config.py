from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in {"true", "1", "yes"}

@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/milaan.db"))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", "./data/uploads")))
    cors_origins: list[str] = field(default_factory=lambda: [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000").split(",") if x.strip()])
    run_worker: bool = field(default_factory=lambda: flag("RUN_WORKER_IN_API", True))
    registration_open: bool = field(default_factory=lambda: flag("ALLOW_REGISTRATION", True))
    enable_demo: bool = field(default_factory=lambda: flag("ENABLE_DEMO", True))
    session_hours: int = field(default_factory=lambda: int(os.getenv("SESSION_HOURS", "12")))
    retention_hours: int = field(default_factory=lambda: int(os.getenv("BATCH_RETENTION_HOURS", "168")))
    extraction_provider: str = field(default_factory=lambda: os.getenv("EXTRACTION_PROVIDER", "manual"))
    gemini_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", ""))
    require_email_verification: bool = field(default_factory=lambda: flag("REQUIRE_EMAIL_VERIFICATION", True))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
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
    demo_seller_password: str = field(default_factory=lambda: os.getenv("DEMO_SELLER_PASSWORD", ""))
    demo_account_id: str = field(default_factory=lambda: os.getenv("DEMO_ACCOUNT_ID", "milaan-main"))
    testing: bool = False

    def __post_init__(self):
        if self.smtp_security not in {"starttls", "ssl"}:
            raise ValueError("SMTP_SECURITY must be starttls or ssl")
        if self.extraction_provider not in {"manual", "gemini"}:
            raise ValueError("EXTRACTION_PROVIDER must be manual or gemini")
        if "*" in self.cors_origins:
            raise ValueError("Set explicit CORS_ORIGINS, not '*'")
        if not 1 <= self.retention_hours <= 8760:
            raise ValueError("BATCH_RETENTION_HOURS must be between 1 and 8760")

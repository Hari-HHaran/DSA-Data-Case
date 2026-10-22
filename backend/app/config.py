"""Application configuration, loaded from environment variables (see .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="LIVES_", extra="ignore")

    app_name: str = "LIVES ONE"
    database_url: str = f"sqlite:///{BASE_DIR / 'lives_one.db'}"
    # Development default only. Always override LIVES_SECRET_KEY outside a local demo.
    secret_key: str = "dev-only-change-me-lives-one"
    access_token_minutes: int = 12 * 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: Path = BASE_DIR / "storage" / "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    # Demo mode exposes the persona picker and the shared demo password.
    demo_mode: bool = True
    demo_password: str = "lives-demo"
    # "mock" is the only adapter shipped with the prototype; "service_layer" is a future stub.
    sap_adapter: str = "mock"
    notification_adapter: str = "mock"
    synthetic_seed: int = 20261028
    # SLA reminder/escalation sweep interval; 0 disables the background loop (tests).
    sla_sweep_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

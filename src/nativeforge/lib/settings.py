"""Environment-backed settings (pydantic-settings)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from nativeforge.lib.demo_isolation import parse_demo_org_ids


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="NativeForge", validation_alias="NF_APP_NAME")
    app_env: str = Field(default="local", validation_alias="NF_APP_ENV")
    database_url: str = Field(
        default="sqlite+pysqlite:///:memory:",
        validation_alias="DATABASE_URL",
    )
    #: Comma-separated UUIDs for demo orgs (must match future `org_type=demo`).
    nf_demo_org_ids: str = Field(default="", validation_alias="NF_DEMO_ORG_IDS")
    #: When True, accept `X-NF-Org-Id` for dev isolation smoke tests (not prod).
    nf_dev_org_headers: bool = Field(
        default=True,
        validation_alias="NF_DEV_ORG_HEADERS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def demo_org_uuid_set(settings: Settings | None = None) -> frozenset:
    """Resolved demo-org allowlist from settings."""
    st = settings or get_settings()
    return parse_demo_org_ids(st.nf_demo_org_ids)

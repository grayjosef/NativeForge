"""Environment-backed settings (pydantic-settings)."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
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

    # ── Gate 97: S3-compatible raw payload body store ──────────────────────
    #
    # All default to empty, which means unconfigured. A blank value is
    # unconfigured too - the detector checks values, not whether the field
    # exists, because a field existing says nothing about an environment.
    #
    # No secret is ever committed: .env is gitignored, and the secret key is a
    # SecretStr so an accidental repr or log line renders `**********` rather
    # than the value.
    raw_payload_object_store_endpoint: str = Field(
        default="",
        validation_alias="RAW_PAYLOAD_OBJECT_STORE_ENDPOINT",
    )
    raw_payload_object_store_bucket: str = Field(
        default="",
        validation_alias="RAW_PAYLOAD_OBJECT_STORE_BUCKET",
    )
    raw_payload_object_store_region: str = Field(
        default="",
        validation_alias="RAW_PAYLOAD_OBJECT_STORE_REGION",
    )
    raw_payload_object_store_access_key_id: str = Field(
        default="",
        validation_alias="RAW_PAYLOAD_OBJECT_STORE_ACCESS_KEY_ID",
    )
    #: SecretStr: `repr()` and `str()` render `**********`. Reading the value
    #: requires an explicit `.get_secret_value()`, which nothing in NativeForge
    #: calls - the body store passes credentials to an injected client, and the
    #: readiness layer only ever reports whether one is present.
    raw_payload_object_store_secret_access_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="RAW_PAYLOAD_OBJECT_STORE_SECRET_ACCESS_KEY",
    )
    #: MinIO and most self-hosted S3-compatible stores need path-style URLs.
    raw_payload_object_store_force_path_style: bool = Field(
        default=False,
        validation_alias="RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE",
    )

    @field_validator("raw_payload_object_store_force_path_style", mode="before")
    @classmethod
    def _blank_means_false(cls, value: object) -> object:
        """An empty env var is "unset", not a parse error.

        `RAW_PAYLOAD_OBJECT_STORE_FORCE_PATH_STYLE=` in a .env file is a
        perfectly ordinary way to write "leave this alone", and without this
        pydantic raises on it - taking the whole Settings object, and therefore
        the app, down over a blank line in a config file.
        """
        if isinstance(value, str) and not value.strip():
            return False
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


def demo_org_uuid_set(settings: Settings | None = None) -> frozenset:
    """Resolved demo-org allowlist from settings."""
    st = settings or get_settings()
    return parse_demo_org_ids(st.nf_demo_org_ids)

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

    # ── Gate 129C: customer auth / OIDC provider configuration ────────────
    #
    # These seven were read straight from `os.environ` and declared nowhere, so
    # `.env` could not supply them (Gate 128) except by the accident of systemd
    # parsing the same file into the process environment (Gate 129A). Declared
    # here, one resolution order serves every caller:
    #
    #     os.environ wins, Settings fills the gaps.
    #
    # os.environ keeps priority so an operator can override the file for a
    # single process, and so tests that set an env var keep working.
    oidc_issuer: str = Field(default="", validation_alias="OIDC_ISSUER")
    oidc_client_id: str = Field(default="", validation_alias="OIDC_CLIENT_ID")
    oidc_audience: str = Field(default="", validation_alias="OIDC_AUDIENCE")
    #: Optional. Derived from `nf_public_origin` + the API callback route when
    #: unset, so an origin alone is enough and the two cannot disagree.
    oidc_callback_url: str = Field(default="", validation_alias="OIDC_CALLBACK_URL")
    nf_public_origin: str = Field(default="", validation_alias="NF_PUBLIC_ORIGIN")
    #: SecretStr, for the reason the object-store secret is one: `repr()` and
    #: `str()` render `**********`, so a settings object reaching a log line or
    #: a traceback carries no credential.
    #:
    #: Unlike the object-store secret, `.get_secret_value()` IS called on these
    #: two -- by `auth_environment_overlay` below, and nowhere else. The auth
    #: detectors decide "is a secret present" by reading an environment mapping,
    #: so the value has to enter that mapping to be counted. It is an in-memory
    #: dict that `os.environ` already holds the same values in; what protects
    #: the value is that every auth service redacts on the way out, which
    #: Gate 121's SECRET_VALUE_KEYS and a Gate 129 test both enforce.
    oidc_client_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="OIDC_CLIENT_SECRET",
    )
    nf_session_signing_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="NF_SESSION_SIGNING_KEY",
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


#: The seven auth keys, and which of them are secrets. Names only.
AUTH_ENV_KEYS: tuple[str, ...] = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "NF_PUBLIC_ORIGIN",
    "NF_SESSION_SIGNING_KEY",
)
AUTH_SECRET_ENV_KEYS: frozenset[str] = frozenset(
    {"OIDC_CLIENT_SECRET", "NF_SESSION_SIGNING_KEY"}
)


def auth_environment_overlay(
    environ: dict[str, str] | None = None,
    *,
    settings: Settings | None = None,
) -> dict[str, str]:
    """The effective auth environment. os.environ wins, Settings fills gaps.

    One resolution order for every auth detector, so `.env`, an
    `EnvironmentFile` and an exported variable cannot disagree about whether a
    key is configured.

    A blank value is unset, not configured -- the same rule the object-store
    detector uses, because a field existing says nothing about an environment.

    Returns a plain dict. Secret values are in it, exactly as they are in
    `os.environ`; nothing here emits them and every auth service redacts on the
    way out.
    """
    import os as _os

    env = dict(_os.environ if environ is None else environ)
    st = settings or get_settings()
    resolved: tuple[tuple[str, str], ...] = (
        ("OIDC_ISSUER", st.oidc_issuer),
        ("OIDC_CLIENT_ID", st.oidc_client_id),
        ("OIDC_AUDIENCE", st.oidc_audience),
        ("OIDC_CALLBACK_URL", st.oidc_callback_url),
        ("NF_PUBLIC_ORIGIN", st.nf_public_origin),
        ("OIDC_CLIENT_SECRET", st.oidc_client_secret.get_secret_value()),
        ("NF_SESSION_SIGNING_KEY", st.nf_session_signing_key.get_secret_value()),
    )
    for key, value in resolved:
        if not str(env.get(key) or "").strip() and str(value or "").strip():
            env[key] = str(value)
    return env


def auth_environment_presence(
    environ: dict[str, str] | None = None,
    *,
    settings: Settings | None = None,
) -> dict[str, bool]:
    """Which auth keys are configured. Booleans only, never values."""
    env = auth_environment_overlay(environ, settings=settings)
    return {k: bool(str(env.get(k) or "").strip()) for k in AUTH_ENV_KEYS}


def demo_org_uuid_set(settings: Settings | None = None) -> frozenset:
    """Resolved demo-org allowlist from settings."""
    st = settings or get_settings()
    return parse_demo_org_ids(st.nf_demo_org_ids)

"""Alembic 0063: identity, affiliation and authority as three columns, not one.

The Gate 177 survey measured the gap in one classification:

```text
nf_authority_proof_records  COLLAPSED
    governs_authority_through_['state']_naming_only_2_of_3
```

One `state` column decided whether somebody could act for a Tribal
government, so "verified" could not say verified *as what*. A person with a
working `@tribe.gov` mailbox has proven control of a mailbox; that is identity
evidence and possibly affiliation evidence, and it says nothing about whether
the Council has authorised them to establish a tenant and speak to funders.

Six tables:

```text
nf_tribal_authority_grants        three independent statuses, one scope
nf_tribal_authority_evidence      what was shown, who judged it, and when
nf_organization_profile_versions  the organisation's account of itself
nf_organization_defaults          what the organisation publishes for all
nf_personal_dashboard_overrides   what one person sets for themselves
nf_organization_invitations       who invited whom, and with what standing
```

## The constraints that carry the gate

`ck_..._authority_may_not_outrank_affiliation` and
`ck_..._authority_may_not_outrank_identity`. A sufficient authority status is
unrepresentable unless affiliation and identity are independently VERIFIED.
This is the collapse, made impossible rather than merely discouraged: no
writer, however careless, can store an authority that rests on
`SELF_ASSERTED` affiliation.

`ck_..._verified_authority_is_signed`. A sufficient authority must name its
verifier, its date and its reason. An authority nobody signed for is the
thing this gate exists to prevent.

`ck_..._no_customer_role_confers_controlling_company`. An invitation offering
`CONTROLLING_COMPANY_ADMIN` from a customer role cannot be written at all, so
the privilege boundary survives a writer that skips the service.

`ck_..._personal_override_is_not_branding` has no counterpart in the Python:
the personal-override table simply HAS no branding columns. One person's
taste is not the Tribe's identity, and the cheapest way to guarantee that is
to leave nowhere to put it.

`ck_..._recognized_phrase_has_classes` keeps the phrase rule honest in the
store: a phrase recorded as RECOGNIZED must name the classes it resolved to,
and a LOOKUP_MISS must not be confused with an organisation that deliberately
said nothing.

Preserves 0056 through 0062.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | None = None
depends_on: str | None = None

GRANTS = "nf_tribal_authority_grants"
EVIDENCE = "nf_tribal_authority_evidence"
PROFILES = "nf_organization_profile_versions"
DEFAULTS = "nf_organization_defaults"
OVERRIDES = "nf_personal_dashboard_overrides"
INVITATIONS = "nf_organization_invitations"

IDENTITY_STATES = ("UNVERIFIED", "VERIFIED", "REVIEW_REQUIRED", "REVOKED", "UNKNOWN")

AFFILIATION_STATES = (
    "UNVERIFIED",
    "SELF_ASSERTED",
    "EVIDENCE_PROVIDED",
    "VERIFIED",
    "REVIEW_REQUIRED",
    "REVOKED",
    "UNKNOWN",
)

AUTHORITY_STATES = (
    "UNVERIFIED",
    "MANUALLY_VERIFIED",
    "DOCUMENT_VERIFIED",
    "ORG_ADMIN_CONFIRMED",
    "REVIEW_REQUIRED",
    "REVOKED",
    "EXPIRED",
    "UNKNOWN",
)

#: Authority states that permit administering - IF the other two allow it.
AUTHORITY_SUFFICIENT = (
    "MANUALLY_VERIFIED",
    "DOCUMENT_VERIFIED",
    "ORG_ADMIN_CONFIRMED",
)

SCOPES = (
    "ADMINISTER_TENANT",
    "MANAGE_MEMBERS",
    "MANAGE_PROFILE",
    "SUBMIT_APPLICATIONS",
)

EVIDENCE_TYPES = (
    "OFFICIAL_TRIBAL_WEBSITE",
    "OFFICIAL_TRIBAL_ROSTER",
    "ORGANIZATION_EMAIL_DOMAIN",
    "ORG_ADMIN_INVITATION",
    "SIGNED_AUTHORIZATION",
    "TRIBAL_RESOLUTION",
    "GOVERNING_AUTHORIZATION",
    "CONTROLLING_COMPANY_VERIFICATION",
    "IDENTITY_PROVIDER_ASSERTION",
    "ORGANIZATION_SPECIFIC_OTHER",
)

DECISIONS = ("PENDING", "ACCEPTED", "REJECTED", "SUPERSEDED", "EXPIRED")

#: Decisions that require a named human. PENDING notably does not: evidence
#: nobody has judged is a queue item, not a warrant.
JUDGED_DECISIONS = ("ACCEPTED", "REJECTED")

ROLES = (
    "CONTROLLING_COMPANY_ADMIN",
    "ORG_SUPER_ADMIN",
    "ORG_ADMIN",
    "ORG_REVIEWER",
    "ORG_MEMBER",
)

CUSTOMER_ROLES = ("ORG_SUPER_ADMIN", "ORG_ADMIN", "ORG_REVIEWER", "ORG_MEMBER")

INVITE_STATES = ("PENDING", "ACCEPTED", "REVOKED", "EXPIRED")

PHRASE_OUTCOMES = ("RECOGNIZED", "AMBIGUOUS", "LOOKUP_MISS", "EXPLICITLY_EMPTY")

ENTITY_TYPES = (
    "FEDERALLY_RECOGNIZED_TRIBE",
    "STATE_RECOGNIZED_TRIBE",
    "TRIBAL_ORGANIZATION",
    "TRIBAL_ENTERPRISE",
    "ALASKA_NATIVE_CORPORATION",
    "NATIVE_HAWAIIAN_ORGANIZATION",
    "NATIVE_NONPROFIT",
    "INTERTRIBAL_CONSORTIUM",
    "OTHER",
    "UNKNOWN",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # `~` is a regex match in PostgreSQL and a bitwise NOT in SQLite; GLOB is
    # SQLite-only. Same semantics, two spellings: '#', one hex character, then
    # anything. Length is constrained separately by the surrounding AND.
    _hex_prefix = (
        "primary_color GLOB '#[0-9a-fA-F]*'"
        if op.get_bind().dialect.name == "sqlite"
        else "primary_color ~ '^#[0-9a-fA-F]'"
    )

    # ---------------- authority grants -------------------------------
    op.create_table(
        GRANTS,
        sa.Column("authority_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("identity_id", sa.Text(), nullable=False),
        # THREE questions. THREE columns. There is deliberately no fourth
        # column summarising them, because a summary is what everything
        # downstream would read instead.
        sa.Column("identity_status", sa.String(length=24), nullable=False),
        sa.Column("affiliation_status", sa.String(length=24), nullable=False),
        sa.Column("authority_status", sa.String(length=24), nullable=False),
        sa.Column("authority_method", sa.String(length=48), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("verified_by", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Text(), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_ids_json", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("identity_status", IDENTITY_STATES),
            name=f"ck_{GRANTS}_identity_status",
        ),
        sa.CheckConstraint(
            _in_list("affiliation_status", AFFILIATION_STATES),
            name=f"ck_{GRANTS}_affiliation_status",
        ),
        sa.CheckConstraint(
            _in_list("authority_status", AUTHORITY_STATES),
            name=f"ck_{GRANTS}_authority_status",
        ),
        sa.CheckConstraint(_in_list("scope", SCOPES), name=f"ck_{GRANTS}_scope"),
        # The collapse, made unrepresentable.
        sa.CheckConstraint(
            f"{_in_list('authority_status', AUTHORITY_SUFFICIENT)} = false "
            "OR affiliation_status = 'VERIFIED'",
            name=f"ck_{GRANTS}_auth_may_not_outrank_affil",
        ),
        sa.CheckConstraint(
            f"{_in_list('authority_status', AUTHORITY_SUFFICIENT)} = false "
            "OR identity_status = 'VERIFIED'",
            name=f"ck_{GRANTS}_auth_may_not_outrank_identity",
        ),
        # An authority nobody signed for cannot be stored.
        sa.CheckConstraint(
            f"{_in_list('authority_status', AUTHORITY_SUFFICIENT)} = false "
            "OR (verified_by IS NOT NULL AND verified_at IS NOT NULL "
            "AND reason IS NOT NULL)",
            name=f"ck_{GRANTS}_verified_authority_is_signed",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR "
            "(revoked_by IS NOT NULL AND revoked_reason IS NOT NULL)",
            name=f"ck_{GRANTS}_revocation_is_attributed",
        ),
    )
    op.create_index(
        f"ix_{GRANTS}_organization", GRANTS, ["organization_id", "authority_status"]
    )
    op.create_index(f"ix_{GRANTS}_identity", GRANTS, ["identity_id"])
    op.create_index(
        f"ix_{GRANTS}_expiring", GRANTS, ["authority_status", "expires_at"]
    )

    # ---------------- authority evidence ------------------------------
    op.create_table(
        EVIDENCE,
        sa.Column("evidence_id", sa.String(length=64), primary_key=True),
        sa.Column("evidence_type", sa.String(length=48), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("subject_identity_id", sa.Text(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=True),
        # A REFERENCE, never the artifact's bytes and never a credential.
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("artifact_ref", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("establishes_identity", sa.Boolean(), nullable=False),
        sa.Column("establishes_affiliation", sa.Boolean(), nullable=False),
        sa.Column("establishes_authority", sa.Boolean(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            _in_list("evidence_type", EVIDENCE_TYPES),
            name=f"ck_{EVIDENCE}_type",
        ),
        sa.CheckConstraint(
            _in_list("decision", DECISIONS), name=f"ck_{EVIDENCE}_decision"
        ),
        # A judged decision names a judge, a reason and a date.
        sa.CheckConstraint(
            f"{_in_list('decision', JUDGED_DECISIONS)} = false "
            "OR (reviewer IS NOT NULL AND reason IS NOT NULL "
            "AND decided_at IS NOT NULL)",
            name=f"ck_{EVIDENCE}_judgement_is_attributed",
        ),
        # A mailbox is not a mandate. The intern and the chairperson share a
        # domain, so this type can never carry the authority flag.
        sa.CheckConstraint(
            "evidence_type <> 'ORGANIZATION_EMAIL_DOMAIN' "
            "OR establishes_authority = false",
            name=f"ck_{EVIDENCE}_email_domain_is_not_authority",
        ),
        sa.CheckConstraint(
            "evidence_type <> 'OFFICIAL_TRIBAL_WEBSITE' "
            "OR establishes_authority = false",
            name=f"ck_{EVIDENCE}_a_website_listing_is_not_auth",
        ),
    )
    op.create_index(
        f"ix_{EVIDENCE}_subject",
        EVIDENCE,
        ["organization_id", "subject_identity_id"],
    )
    op.create_index(f"ix_{EVIDENCE}_decision", EVIDENCE, ["decision", "evidence_type"])

    # ---------------- organisation profile versions -------------------
    op.create_table(
        PROFILES,
        sa.Column("profile_version_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("version_ordinal", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_id", sa.String(length=64), nullable=True),
        sa.Column("entity_type", sa.String(length=48), nullable=False),
        sa.Column("values_json", sa.Text(), nullable=False),
        sa.Column("phrase_resolutions_json", sa.Text(), nullable=False),
        sa.Column("unresolved_phrase_count", sa.Integer(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            _in_list("entity_type", ENTITY_TYPES), name=f"ck_{PROFILES}_entity_type"
        ),
        sa.CheckConstraint(
            "version_ordinal >= 1", name=f"ck_{PROFILES}_version_is_a_version"
        ),
        sa.CheckConstraint(
            "version_ordinal = 1 OR supersedes_version_id IS NOT NULL",
            name=f"ck_{PROFILES}_later_ver_names_its_pred",
        ),
        sa.CheckConstraint(
            "supersedes_version_id IS NULL "
            "OR supersedes_version_id <> profile_version_id",
            name=f"ck_{PROFILES}_no_self_supersession",
        ),
        # The phrase rule, kept honest in the store: an unresolved phrase
        # must send somebody to look, never resolve quietly to nothing.
        sa.CheckConstraint(
            "unresolved_phrase_count = 0 OR review_required = true",
            name=f"ck_{PROFILES}_unres_phrases_ask_review",
        ),
        sa.CheckConstraint(
            "unresolved_phrase_count >= 0",
            name=f"ck_{PROFILES}_unresolved_count_is_a_count",
        ),
    )
    op.create_index(
        f"ix_{PROFILES}_organization",
        PROFILES,
        ["organization_id", "version_ordinal"],
    )

    # ---------------- organisation defaults ---------------------------
    op.create_table(
        DEFAULTS,
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("version_ordinal", sa.Integer(), nullable=False),
        sa.Column("logo_ref", sa.Text(), nullable=True),
        sa.Column("symbol_ref", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("secondary_color", sa.String(length=7), nullable=True),
        sa.Column("accent_color", sa.String(length=7), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("tile_order_json", sa.Text(), nullable=True),
        sa.Column("hidden_tiles_json", sa.Text(), nullable=True),
        sa.Column("density", sa.String(length=16), nullable=True),
        sa.Column("landing_tile", sa.String(length=32), nullable=True),
        # Publishing is deliberate, attributed and versioned.
        sa.Column("published_by", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "version_ordinal", name=f"pk_{DEFAULTS}"
        ),
        sa.CheckConstraint(
            "version_ordinal >= 1", name=f"ck_{DEFAULTS}_version_is_a_version"
        ),
        sa.CheckConstraint(
            "density IS NULL OR density IN ('COMFORTABLE', 'COMPACT')",
            name=f"ck_{DEFAULTS}_density",
        ),
        # Colours are hex or absent. There is no free-form style column here
        # and there must not become one.
        sa.CheckConstraint(
            "primary_color IS NULL OR "
            f"({_hex_prefix} AND "
            "(length(primary_color) = 4 OR length(primary_color) = 7))",
            name=f"ck_{DEFAULTS}_primary_color_is_hex",
        ),
    )

    # ---------------- personal overrides ------------------------------
    # NOTE: no branding columns exist here, on purpose. One person's taste is
    # not the Tribe's identity, and the cheapest way to guarantee a personal
    # setting cannot reach the organisation's brand is to give it nowhere to
    # live.
    op.create_table(
        OVERRIDES,
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("identity_id", sa.Text(), nullable=False),
        sa.Column("tile_order_json", sa.Text(), nullable=True),
        sa.Column("hidden_tiles_json", sa.Text(), nullable=True),
        sa.Column("density", sa.String(length=16), nullable=True),
        sa.Column("landing_tile", sa.String(length=32), nullable=True),
        sa.Column("saved_filters_json", sa.Text(), nullable=True),
        sa.Column("watch_preferences_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "identity_id", name=f"pk_{OVERRIDES}"
        ),
        sa.CheckConstraint(
            "density IS NULL OR density IN ('COMFORTABLE', 'COMPACT')",
            name=f"ck_{OVERRIDES}_density",
        ),
    )

    # ---------------- invitations -------------------------------------
    op.create_table(
        INVITATIONS,
        sa.Column("invitation_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("invited_by", sa.Text(), nullable=True),
        sa.Column("invited_by_role", sa.String(length=32), nullable=False),
        sa.Column("invited_subject_ref", sa.Text(), nullable=False),
        sa.Column("offered_role", sa.String(length=32), nullable=False),
        sa.Column("invite_state", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Text(), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            _in_list("invited_by_role", ROLES), name=f"ck_{INVITATIONS}_inviter_role"
        ),
        sa.CheckConstraint(
            _in_list("offered_role", ROLES), name=f"ck_{INVITATIONS}_offered_role"
        ),
        sa.CheckConstraint(
            _in_list("invite_state", INVITE_STATES), name=f"ck_{INVITATIONS}_state"
        ),
        # The privilege boundary, surviving a writer that skips the service.
        sa.CheckConstraint(
            "offered_role <> 'CONTROLLING_COMPANY_ADMIN' "
            f"OR {_in_list('invited_by_role', CUSTOMER_ROLES)} = false",
            name=f"ck_{INVITATIONS}_no_cust_role_confers_ctrl_co",
        ),
        # An ordinary member may not invite anybody at all.
        sa.CheckConstraint(
            "invited_by_role NOT IN ('ORG_MEMBER', 'ORG_REVIEWER')",
            name=f"ck_{INVITATIONS}_inviter_may_invite",
        ),
        sa.CheckConstraint(
            "invite_state <> 'REVOKED' "
            "OR (revoked_by IS NOT NULL AND revoked_reason IS NOT NULL)",
            name=f"ck_{INVITATIONS}_revocation_is_attributed",
        ),
    )
    op.create_index(
        f"ix_{INVITATIONS}_organization",
        INVITATIONS,
        ["organization_id", "invite_state"],
    )
    op.create_index(
        f"ix_{INVITATIONS}_pending", INVITATIONS, ["invite_state", "expires_at"]
    )


def downgrade() -> None:
    op.drop_index(f"ix_{INVITATIONS}_pending", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_organization", table_name=INVITATIONS)
    op.drop_table(INVITATIONS)

    op.drop_table(OVERRIDES)
    op.drop_table(DEFAULTS)

    op.drop_index(f"ix_{PROFILES}_organization", table_name=PROFILES)
    op.drop_table(PROFILES)

    op.drop_index(f"ix_{EVIDENCE}_decision", table_name=EVIDENCE)
    op.drop_index(f"ix_{EVIDENCE}_subject", table_name=EVIDENCE)
    op.drop_table(EVIDENCE)

    op.drop_index(f"ix_{GRANTS}_expiring", table_name=GRANTS)
    op.drop_index(f"ix_{GRANTS}_identity", table_name=GRANTS)
    op.drop_index(f"ix_{GRANTS}_organization", table_name=GRANTS)
    op.drop_table(GRANTS)

"""Authenticated demo workspace — fixture data only, no tenant RLS."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, status

from nativeforge.services.customer_demo_story_service import build_demo_story
from nativeforge.services.customer_session_verifier_service import verify_session_cookie
from nativeforge.services.customer_workspace_lane_service import resolve_workspace_lane

router = APIRouter(prefix="/api/demo-workspace", tags=["demo-workspace"])

SESSION_COOKIE_NAME = "nf_session"


def require_demo_workspace_lane(
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    parsed = verify_session_cookie(cookie_value=nf_session, membership_verified=False)
    if not parsed.get("session_cookie_valid") or not parsed.get("principal_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required"},
        )
    lane = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id=parsed.get("principal_id"),
        organization_id=parsed.get("organization_id"),
        membership_verified=False,
    )
    if lane["workspace_lane"] != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "demo_workspace_lane_required",
                "workspace_lane": lane["workspace_lane"],
            },
        )
    return lane


@router.get("/summary")
def demo_workspace_summary(
    _lane: Annotated[dict[str, Any], Depends(require_demo_workspace_lane)],
) -> dict[str, Any]:
    """FIND / PURSUE / GOVERN illustrative payload for unaffiliated users."""
    story = build_demo_story()
    return {
        "schema_version": "nf_demo_workspace_summary_v1",
        "workspace_lane": "demo",
        "fixture_feed": True,
        "demo_provenance": "nf_customer_demo_story_v1",
        "title": "NativeForge Demo Workspace",
        "tagline": "Funding intelligence. Built for Native nations.",
        "introduction": (
            "Explore how NativeForge finds, evaluates, pursues, and governs "
            "funding opportunities."
        ),
        "environment_label": "DEMO ENVIRONMENT",
        "find": {
            "headline": "Discover and qualify the right opportunities.",
            "opportunities": story.get("recommendations") or [],
            "feed": story.get("feed"),
        },
        "pursue": {
            "headline": "Move every opportunity from decision to submission.",
            "pursuit": story.get("pursuit"),
        },
        "govern": {
            "headline": "Keep the work accountable, compliant, and under control.",
            "dashboard": story.get("dashboard"),
            "trust_panel": story.get("trust_panel"),
        },
        "education": _education_cards(),
        "upgrade": {
            "cta_label": "Activate your organization",
            "summary": (
                "Purchase and provisioning connect commercial entitlement to your "
                "organization profile and real workspace. Tribal authority remains "
                "a separate review."
            ),
            "contact_path": "/?view=settings",
        },
    }


def _education_cards() -> list[dict[str, str]]:
    return [
        {
            "id": "why_opportunity",
            "title": "Why this opportunity appears",
            "body": (
                "NativeForge scores relevance and eligibility from source "
                "documents and your organization's profile when you have one."
            ),
        },
        {
            "id": "requirements",
            "title": "Where requirements come from",
            "body": (
                "Requirements are extracted from notices and NOFOs with citations "
                "so your team can verify every claim."
            ),
        },
        {
            "id": "pursue",
            "title": "What happens when you pursue",
            "body": (
                "Pursuing creates accountable tasks, deadlines, and a work package "
                "your team can review before submission."
            ),
        },
        {
            "id": "govern",
            "title": "What governance means",
            "body": (
                "Governance keeps decisions, provenance, and deadlines visible "
                "so nothing slips through during a long application cycle."
            ),
        },
        {
            "id": "after_purchase",
            "title": "What changes after purchase",
            "body": (
                "Your organization's real opportunities, documents, and decisions "
                "live in a separate workspace backed by your data — not this demo."
            ),
        },
    ]

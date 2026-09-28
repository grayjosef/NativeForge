"""Attention items come from real state, never invented counts."""

from nativeforge.services.customer_attention_service import build_attention_items


def test_profile_gap_and_deadline_only() -> None:
    result = build_attention_items(
        profile_complete=False,
        sparks=[
            {"id": "s1", "title": "ICDBG", "agency": "HUD", "close_date": "2099-01-01"}
        ],
        tasks=[{"id": "t1", "title": "Budget", "blocked": True}],
        membership_count=1,
    )
    kinds = {item["kind"] for item in result["items"]}
    assert "organization" in kinds
    assert "blocker" in kinds
    assert result["fabricated"] is False
    assert result["email_required"] is False

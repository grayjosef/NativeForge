#!/usr/bin/env python3
"""Auth0/OIDC validation smoke — never prints secrets."""

from __future__ import annotations

import json

from nativeforge.services.auth0_validation_smoke_service import (
    run_auth0_validation_smoke,
)


def main() -> int:
    result = run_auth0_validation_smoke()
    # Redact any accidental secret-like keys
    safe = {
        k: v
        for k, v in result.items()
        if k
        not in {
            "OIDC_CLIENT_SECRET",
            "client_secret",
            "client_secret_value",
        }
    }
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0 if result.get("overall_status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

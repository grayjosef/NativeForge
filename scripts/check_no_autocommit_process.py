import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
doc = root / "docs" / "HITP_COMMIT_GATE.md"
val = root / "scripts" / "nativeforge_full_validation.sh"
doc_text = doc.read_text() if doc.exists() else ""
val_text = val.read_text() if val.exists() else ""
checks = {
    "HITP doc exists": doc.exists(),
    "HITP block exists": "HITP COMMIT APPROVAL REQUIRED" in doc_text,
    "approve commit phrase exists": "approve commit" in doc_text,
    "commit it phrase exists": "commit it" in doc_text,
    "go commit phrase exists": "go commit" in doc_text,
    "validation script exists": val.exists(),
    "frontend package handling exists": "frontend/package.json" in val_text,
    "frontend build exists": "npm run build" in val_text,
    "frontend typecheck exists": "npm run typecheck" in val_text,
    "frontend lint handling exists": "npm run lint" in val_text,
    "frontend test handling exists": "npm test" in val_text,
    "no auto git commit": "git commit" not in val_text,
}
failed = False
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + f": {name}")
    failed = failed or not ok
sys.exit(1 if failed else 0)

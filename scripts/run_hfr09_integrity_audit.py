from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "results" / "E103_HFR09_INTEGRITY_AUDIT.json"
COMMAND = [sys.executable, "-m", "cymatic_engine.hfr09_integrity"]


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        COMMAND,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        check=False,
    )

    if proc.stderr.strip():
        print(proc.stderr, file=sys.stderr, end="")

    try:
        report = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        print(
            f"ERROR: integrity module did not return valid JSON: {exc}",
            file=sys.stderr,
        )
        if proc.stdout:
            print(proc.stdout[:4000], file=sys.stderr)
        return 2

    if not isinstance(report, dict):
        print("ERROR: audit report must be a JSON object.", file=sys.stderr)
        return 2

    if report.get("audit") != "HFR09_ASSET_INTEGRITY":
        print("ERROR: unexpected audit identity.", file=sys.stderr)
        return 2

    if report.get("fail_closed") is not True:
        print("ERROR: fail_closed must be true.", file=sys.stderr)
        return 2

    issues = report.get("issues")
    count = report.get("issue_count")
    status = report.get("status")

    if not isinstance(issues, list) or count != len(issues):
        print("ERROR: issue_count does not match issues.", file=sys.stderr)
        return 2

    if status == "PASS":
        if count != 0 or proc.returncode != 0:
            print("ERROR: inconsistent PASS status or exit code.", file=sys.stderr)
            return 2
    elif status == "BLOCKED":
        if count == 0 or proc.returncode != 1:
            print("ERROR: inconsistent BLOCKED status or exit code.", file=sys.stderr)
            return 2
    else:
        print(f"ERROR: unsupported audit status: {status!r}", file=sys.stderr)
        return 2

    # Preserve the previous report before replacing it with validated JSON.
    if REPORT.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = REPORT.with_name(REPORT.name + f".bak-ci-{stamp}")
        suffix = 1
        while backup.exists():
            backup = REPORT.with_name(
                REPORT.name + f".bak-ci-{stamp}-{suffix}"
            )
            suffix += 1
        backup.write_bytes(REPORT.read_bytes())
        print(f"Previous report backed up: {backup.relative_to(ROOT)}")

    serialized = json.dumps(
        report, ensure_ascii=False, indent=2
    ) + "\n"
    REPORT.write_text(serialized, encoding="utf-8")

    # Read the saved file back independently before returning the audit result.
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    if saved.get("audit") != "HFR09_ASSET_INTEGRITY":
        print("ERROR: saved report failed identity validation.", file=sys.stderr)
        return 2
    if saved.get("issue_count") != len(saved.get("issues", [])):
        print("ERROR: saved report failed count validation.", file=sys.stderr)
        return 2

    print(f"Audit status: {status}")
    print(f"Issue count: {count}")
    print(f"Fail closed: {saved['fail_closed']}")
    print(f"Validated report: {REPORT.relative_to(ROOT)}")

    # Preserve the integrity gate's actual result: BLOCKED remains exit code 1.
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
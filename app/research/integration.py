from dataclasses import dataclass
from pathlib import Path
import json

from app.workbench import _apply_evidence_gate


@dataclass(frozen=True)
class ResearchGateStatus:
    name: str
    status: str
    detail: str


class ScientificResearchController:
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).resolve().parents[2])
        self.results = self.root / "results"

    def get_status(self):
        checks = {
            "Real Corpus": "REAL_CORPUS_RUN_v713_STATUS.json",
            "Scientific Validation": "SCIENTIFIC_VALIDATION_v714_STATUS.json",
        }

        output = []

        for name, filename in checks.items():
            path = self.results / filename

            if not path.exists():
                output.append(
                    ResearchGateStatus(
                        name=name,
                        status="BLOCKED",
                        detail=f"Status file not found: {filename}",
                    )
                )
                continue

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                output.append(
                    ResearchGateStatus(
                        name=name,
                        status="BLOCKED",
                        detail=f"Invalid status JSON: {exc}",
                    )
                )
                continue

            # Reuse the same fail-closed evidence gate as the primary
            # research UI so this secondary panel cannot expose an ungated
            # READY/COMPLETE status from a status artifact.
            data = _apply_evidence_gate(filename, data)
            status = str(
                data.get("status")
                or data.get("release_status")
                or "UNKNOWN"
            )
            detail = f"Read from {filename}"
            if data.get("gate_reason"):
                detail += f"; {data['gate_reason']}"
            missing = data.get("missing_evidence_flags")
            if missing:
                detail += " Missing flags: " + ", ".join(missing)

            output.append(
                ResearchGateStatus(
                    name=name,
                    status=status,
                    detail=detail,
                )
            )

        output.extend(
            [
                ResearchGateStatus(
                    name="MMS-FA",
                    status="BLOCKED",
                    detail="Requires real MMS-FA execution.",
                ),
                ResearchGateStatus(
                    name="Character → Phone Projection",
                    status="BLOCKED",
                    detail="Requires explicit validated mapping.",
                ),
                ResearchGateStatus(
                    name="680 Candidate Dataset",
                    status="BLOCKED",
                    detail="Requires exactly 680 real candidates.",
                ),
                ResearchGateStatus(
                    name="Physical Validation",
                    status="EVIDENCE_GATE_PENDING",
                    detail="Requires qualifying physical evidence.",
                ),
                ResearchGateStatus(
                    name="Release Gate",
                    status="BLOCKED",
                    detail="Scientific release criteria are not yet satisfied.",
                ),
            ]
        )

        return output


def get_research_status(root=None):
    return ScientificResearchController(root).get_status()

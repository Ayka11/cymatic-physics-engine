from pathlib import Path
import json

def build_scientific_report(record, path):
    pv=record["pv_result"]
    lines=[
        "# Cymatic Physics Engine — Scientific Experiment Report",
        "",
        f"Schema version: {record['schema_version']}",
        f"Scientific status: **{record['scientific_status']}**",
        f"Evidence level: **{record['evidence_level']}**",
        "",
        "## Reproducibility",
        f"- Source SHA-256: `{record['source_hash']}`",
        f"- Calibration SHA-256: `{record['calibration_hash']}`",
        f"- Record SHA-256: `{record['record_hash']}`",
        "",
        "## Pipeline",
        " → ".join(record["stages"]),
        "",
        "## Physical validation",
    ]
    for level,data in pv.get("gates",{}).items():
        lines.append(f"- {level}: {'PASS' if data.get('passed') else 'FAIL'}")
    lines += [
        "",
        "## Claim guard",
        f"- Real physical-chain claim permitted: **{record['claim_guard']['real_physical_chain_claim']}**",
        f"- Phoneme identity claim permitted: **{record['claim_guard']['phoneme_identity_claim']}**",
        f"- Glyph identity claim permitted: **{record['claim_guard']['glyph_identity_claim']}**",
        "",
        "The report distinguishes computational output from experimentally validated evidence.",
    ]
    Path(path).write_text("\n".join(lines)+"\n",encoding="utf-8")
    return path

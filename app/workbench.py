import csv
import io
import json
import tempfile
from pathlib import Path

import gradio as gr
import numpy as np

from cymatic_engine.experiment.runner import run_experiment_analysis, run_synthetic_reference
from cymatic_engine.experiment.models import ExperimentManifest
from cymatic_engine.calibration.models import CalibrationManifest
from cymatic_engine.calibration.validation import evaluate_physical_validation
from cymatic_engine.experiment.physical_validation_adapter import build_physical_validation_record

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PROTOCOL = ROOT / "CPE_PHYSICAL_MEASUREMENT_PROTOCOL_A_Z.md"


def _json(x):
    return json.dumps(x, indent=2, ensure_ascii=False, default=str)


def _apply_evidence_gate(name, data):
    """Apply artifact-specific fail-closed evidence rules without conflating implementation and evidence."""
    if not isinstance(data, dict):
        return {"status": "BLOCKED", "file": name, "evidence_gate": "BLOCKED",
                "gate_reason": "Status artifact must be a JSON object."}

    requirements = {
        "REAL_CORPUS_RUN_v713_STATUS.json": (
            "real_corpus_present", "real_mms_fa_execution_performed",
        ),
        "SCIENTIFIC_VALIDATION_v714_STATUS.json": (
            "real_corpus_present", "real_mms_fa_execution_performed",
            "independent_reference_present", "scientific_accuracy_claim_allowed",
        ),
        "V7_09_STATUS.json": (
            "real_mms_fa_execution_available_in_package", "real_mms_fa_execution_performed",
            "benchmark_result_emitted", "v707_pass", "v708_manifest_pass",
            "independent_deterministic_rerun_pass",
        ),
        "DATASET_BUILDER_STATUS.json": (
            "real_mms_fa_execution_available_in_package", "real_mms_fa_execution_performed",
            "upstream_candidate_qc_pass", "dataset_emitted",
        ),
        "CANDIDATE_QC_STATUS.json": (
            "real_mms_fa_execution_available_in_package", "real_mms_fa_execution_performed",
            "alignment_output_present", "candidate_qc_executed", "selection_emitted",
        ),
        "ALIGNMENT_VALIDATOR_STATUS.json": (
            "fail_closed", "real_mms_fa_execution_performed",
            "alignment_output_present", "validation_executed", "validation_result_emitted",
        ),
        "MMS_FA_STATUS.json": ("model_weights_available", "model_execution_performed"),
    }
    result = dict(data)
    declared_status = str(data.get("status", "UNKNOWN")).upper()
    result["declared_status"] = data.get("status", "UNKNOWN")

    # An explicit BLOCKED state is never promoted by UI-level checks.
    if declared_status == "BLOCKED" and name != "REPRODUCIBILITY_MANIFEST_v708.json":
        result["status"] = "BLOCKED"
        result["evidence_gate"] = "BLOCKED"
        result.setdefault("gate_reason", "Artifact explicitly declares BLOCKED.")
        return result

    # A reproducibility manifest must remain blocked when it declares failures,
    # even if its top-level status is edited inconsistently.
    if name == "REPRODUCIBILITY_MANIFEST_v708.json":
        failures = data.get("failures")
        policy = data.get("reproducibility_policy")
        required_statuses = policy.get("upstream_statuses_required", ["PASS", "PASS_WITH_REVIEW"]) if isinstance(policy, dict) else ["PASS", "PASS_WITH_REVIEW"]
        artifact_statuses = data.get("artifacts", {})
        bad_upstream = []
        if isinstance(artifact_statuses, dict):
            for key, artifact in artifact_statuses.items():
                if not isinstance(artifact, dict) or str(artifact.get("status", "UNKNOWN")).upper() not in required_statuses:
                    bad_upstream.append(key)
        missing = []
        if data.get("fail_closed") is not True:
            missing.append("fail_closed")
        if not isinstance(failures, list) or failures:
            missing.append("failures_empty")
        if bad_upstream:
            missing.extend("upstream_pass:" + key for key in bad_upstream)
        blocked = bool(missing)
        result["status"] = "BLOCKED" if blocked else declared_status
        result["evidence_gate"] = "BLOCKED" if blocked else "EVIDENCE_FLAGS_PRESENT"
        if blocked:
            result["gate_reason"] = "Manifest contains failures or upstream artifacts that are not PASS/PASS_WITH_REVIEW."
            result["missing_evidence_flags"] = missing
        return result

    # A corpus-balance report needs an actual input dataset and an emitted QC result.
    requirements["CORPUS_BALANCE_QC_STATUS.json"] = (
        "dataset_present", "qc_executed", "qc_report_emitted",
    )
    gated_names = set(requirements)
    if name not in gated_names:
        return result

    required = requirements.get(name, ())
    missing = [field for field in required if data.get(field) is not True]
    # Readiness milestones retain their own valid labels, but the release-pipeline
    # artifacts must explicitly pass their stage-specific checks.
    allowed_statuses = {
        "REAL_CORPUS_RUN_v713_STATUS.json": {"PASS", "PASS_WITH_REVIEW", "READY_FOR_REAL_CORPUS"},
        "SCIENTIFIC_VALIDATION_v714_STATUS.json": {"PASS", "PASS_WITH_REVIEW", "COMPLETE"},
    }
    accepted_statuses = allowed_statuses.get(name, {"PASS", "PASS_WITH_REVIEW"})
    passing_status = declared_status in accepted_statuses
    if not passing_status:
        missing.append("status:PASS_or_PASS_WITH_REVIEW")

    result["evidence_gate"] = "BLOCKED" if missing else "EVIDENCE_FLAGS_PRESENT"
    if missing:
        result["status"] = "BLOCKED"
        result["gate_reason"] = "Required evidence or a passing artifact status is missing."
        result["missing_evidence_flags"] = missing
    return result


def _status_file(name):
    p = RESULTS / name
    if not p.exists():
        return {"status": "UNAVAILABLE", "file": name}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return _apply_evidence_gate(name, data)
    except Exception as exc:
        return {"status": "UNREADABLE", "file": name, "error": str(exc)}


def _plot_frf(result):
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot(result.frequency_hz, np.abs(result.frf))
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("|FRF|")
        ax.set_title("Measured FRF magnitude")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        return fig
    except Exception:
        return None


def _parse_csv(file_obj):
    if not file_obj:
        raise ValueError("Upload a CSV file containing frequency_hz, force and response columns.")
    path = getattr(file_obj, "name", file_obj)
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("CSV contains no data rows.")
    required = {"frequency_hz", "force", "response"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))
    f = np.asarray([float(r["frequency_hz"]) for r in rows], dtype=float)
    force = np.asarray([float(r["force"]) for r in rows], dtype=float)
    response = np.asarray([float(r["response"]) for r in rows], dtype=float)
    if len(f) < 32 or len(force) != len(response):
        raise ValueError("Insufficient or inconsistent measurement rows.")
    if not np.all(np.isfinite(f)) or not np.all(np.isfinite(force)) or not np.all(np.isfinite(response)):
        raise ValueError("CSV contains non-finite measurement values.")
    return f, force, response


def _make_manifest(experiment_id, sample_rate, plate_id, notes):
    from datetime import datetime, timezone
    return ExperimentManifest(
        experiment_id=experiment_id or "CPE-REAL-UNSPECIFIED",
        plate_id=plate_id or "UNSPECIFIED",
        date_utc=datetime.now(timezone.utc).isoformat(),
        operator="HF_USER",
        acquisition={"sample_rate_hz": float(sample_rate), "input_source": "user_supplied_measurement"},
        excitation={"description": "user-supplied measurement"},
        sensors={"description": "user-supplied measurement"},
        notes=notes or "",
    )


def run_synthetic():
    result = run_synthetic_reference()
    return _json(result), "COMPUTATIONAL ONLY — synthetic reference; no physical evidence."


def run_real_measurement(csv_file, sample_rate, experiment_id, plate_id, notes, nperseg):
    try:
        f, force, response = _parse_csv(csv_file)
        manifest = _make_manifest(experiment_id, sample_rate, plate_id, notes)
        result = run_experiment_analysis(
            force, response, float(sample_rate), manifest, nperseg=int(nperseg)
        )
        payload = {
            "status": "REAL_MEASUREMENT_ANALYSIS_COMPLETED",
            "experiment_id": manifest.experiment_id,
            "manifest_hash": manifest.content_hash(),
            "frequency_bins": int(len(result.frequency_hz)),
            "peak_frequencies_hz": result.peak_frequencies_hz.tolist(),
            "metrics": result.metrics,
            "warnings": list(result.warnings),
            "scientific_note": "Analysis of supplied measurement data is not physical validation by itself; calibration and independent validation remain required.",
        }
        return _json(payload), _plot_frf(result)
    except Exception as exc:
        return _json({"status": "BLOCKED", "error": str(exc)}), None


def make_calibration(level, plate_id, material, acquisition, sensor_chain, excitation, notes):
    manifest = CalibrationManifest(
        calibration_id=f"CPE-CAL-{(plate_id or 'UNSPECIFIED').replace(' ', '_')}",
        level=level or "CAL-UNSPECIFIED",
        plate_id=plate_id or "UNSPECIFIED",
        material={"description": material or ""},
        acquisition={"description": acquisition or ""},
        sensor_chain={"description": sensor_chain or ""},
        excitation={"description": excitation or ""},
        provenance={"notes": notes or "", "source": "user-entered-calibration-metadata"},
    )
    return _json({"status": "CALIBRATION_MANIFEST_CREATED",
                   "calibration_hash": manifest.content_hash(),
                   "manifest": manifest.__dict__})


def validate_measurements(level, metrics_text, thresholds_text, warnings):
    try:
        metrics = json.loads(metrics_text or "{}")
        thresholds = json.loads(thresholds_text or "{}")
        if not isinstance(metrics, dict) or not isinstance(thresholds, dict):
            raise ValueError("Metrics and thresholds must be JSON objects.")
        result = evaluate_physical_validation(level or "PV-UNSPECIFIED", metrics, thresholds,
                                               tuple(x.strip() for x in (warnings or "").splitlines() if x.strip()))
        return _json({
            "status": "PHYSICAL_VALIDATION_RESULT",
            "level": result.level,
            "passed": result.passed,
            "metrics": result.metrics,
            "warnings": list(result.warnings),
            "provenance_hash": result.provenance_hash,
            "scientific_note": "Pass/fail reflects only the supplied metrics and thresholds. Threshold selection and measurement provenance must be independently justified.",
        })
    except Exception as exc:
        return _json({"status": "BLOCKED", "error": str(exc)})


def end_to_end_from_validation(level, calibration_hash, source_hash, metrics_text, thresholds_text):
    try:
        metrics = json.loads(metrics_text or "{}")
        thresholds = json.loads(thresholds_text or "{}")
        if not source_hash or not calibration_hash:
            raise ValueError("Real source SHA-256 and calibration SHA-256 are required.")
        result = build_physical_validation_record(
            source_hash=source_hash,
            calibration_hash=calibration_hash,
            level=level or "PV-UNSPECIFIED",
            metrics=metrics,
            thresholds=thresholds,
        )
        return _json(result)
    except Exception as exc:
        return _json({"status": "BLOCKED", "error": str(exc)})


def protocol_text():
    if not PROTOCOL.exists():
        return "Protocol file is unavailable in this release."
    return PROTOCOL.read_text(encoding="utf-8")


def build_app():
    with gr.Blocks(title="Cymatic Physics Engine — Scientific Research Workbench") as demo:
        gr.Markdown("# 🌊 Cymatic Physics Engine — Scientific Research Workbench")
        gr.Markdown(
            "A research interface for computational experiments, supplied physical measurements, "
            "calibration records, physical validation, the A–Z measurement protocol, HFR-09 REAL assets, "
            "and reproducible evidence records."
        )

        with gr.Tabs():
            with gr.Tab("🧪 Measurement Analysis"):
                gr.Markdown("""### Analyze experimental data

Use **Synthetic Reference** only as a computational control. Use **Real Measurement Analysis** for supplied measured data. Neither path is physical validation by itself.""")
                with gr.Row():
                    syn_btn = gr.Button("Run Synthetic Reference", variant="secondary")
                    syn_status = gr.Code(label="Synthetic result", language="json")
                    syn_note = gr.Textbox(label="Evidence status")
                syn_btn.click(run_synthetic, outputs=[syn_status, syn_note])

                gr.Markdown("#### Real measurement analysis")
                csv_in = gr.File(label="Measurement CSV", file_types=[".csv"])
                with gr.Row():
                    sr = gr.Number(value=16000, label="Sample rate (Hz)")
                    expid = gr.Textbox(value="CPE-REAL-001", label="Experiment ID")
                    plate = gr.Textbox(value="PLATE-001", label="Plate ID")
                    nper = gr.Number(value=4096, label="nperseg")
                notes = gr.Textbox(label="Experiment notes")
                run_btn = gr.Button("Run Real Measurement Analysis", variant="primary")
                real_json = gr.Code(label="Experiment result", language="json")
                frf_plot = gr.Plot(label="FRF magnitude")
                run_btn.click(
                    run_real_measurement,
                    inputs=[csv_in, sr, expid, plate, notes, nper],
                    outputs=[real_json, frf_plot],
                )
                gr.Markdown(
                    "**Evidence guard:** this analysis can process real supplied data, but it does not "
                    "automatically claim physical validation. Calibration, provenance and independent validation remain required."
                )

            with gr.Tab("🎛 Calibration"):
                gr.Markdown("### Create an auditable calibration manifest from the experimental setup.")
                cal_level = gr.Dropdown(["CAL-001","CAL-002","CAL-003","CAL-004","CAL-005","CAL-006","CAL-007"],
                                        value="CAL-001", label="Calibration level")
                cal_plate = gr.Textbox(value="PLATE-001", label="Plate ID")
                material = gr.Textbox(label="Material / plate description")
                acquisition = gr.Textbox(label="Acquisition chain")
                sensor = gr.Textbox(label="Sensor chain")
                excitation = gr.Textbox(label="Excitation / actuator")
                cal_notes = gr.Textbox(label="Calibration notes")
                cal_btn = gr.Button("Create Calibration Manifest")
                cal_out = gr.Code(label="Calibration manifest", language="json")
                cal_btn.click(make_calibration,
                              inputs=[cal_level, cal_plate, material, acquisition, sensor, excitation, cal_notes],
                              outputs=cal_out)

            with gr.Tab("🔬 Physical Validation"):
                gr.Markdown(
                    "Enter measured metrics and pre-defined thresholds. The engine is fail-closed: "
                    "missing metrics, thresholds or provenance do not produce physical evidence."
                )
                pv_level = gr.Textbox(value="PV-REAL-001", label="Validation level")
                metrics = gr.Code(value='{"normalized_rmse": 0.0}', language="json", label="Measured metrics JSON")
                thresholds = gr.Code(value='{"normalized_rmse": 0.1}', language="json", label="Thresholds JSON")
                warnings = gr.Textbox(label="Warnings (one per line)")
                pv_btn = gr.Button("Evaluate Physical Validation", variant="primary")
                pv_out = gr.Code(label="Validation result", language="json")
                pv_btn.click(validate_measurements, inputs=[pv_level, metrics, thresholds, warnings], outputs=pv_out)

                gr.Markdown("#### End-to-end evidence record")
                source_hash = gr.Textbox(label="Real source SHA-256")
                calibration_hash = gr.Textbox(label="Calibration SHA-256")
                e2e_btn = gr.Button("Build End-to-End Record")
                e2e_out = gr.Code(label="End-to-end record", language="json")
                e2e_btn.click(end_to_end_from_validation,
                              inputs=[pv_level, calibration_hash, source_hash, metrics, thresholds],
                              outputs=e2e_out)

            with gr.Tab("📐 Physical Experiment Protocol"):
                gr.Markdown("## CPE Physical Measurement Protocol A–Z")
                gr.Markdown(
                    "This is the experimental protocol. The interface does not treat a protocol document "
                    "as evidence that an experiment was performed."
                )
                gr.Markdown(protocol_text())
                gr.File(value=str(PROTOCOL) if PROTOCOL.exists() else None,
                        label="Download full protocol", interactive=False)

            with gr.Tab("📊 Analysis & Reproducibility"):
                gr.Markdown("### Scientific status files")
                names = [
                    "REAL_CORPUS_RUN_v713_STATUS.json",
                    "SCIENTIFIC_VALIDATION_v714_STATUS.json",
                    "REPRODUCIBILITY_MANIFEST_v708.json",
                    "V7_09_STATUS.json",
                    "CORPUS_BALANCE_QC_STATUS.json",
                    "DATASET_BUILDER_STATUS.json",
                    "CANDIDATE_QC_STATUS.json",
                    "ALIGNMENT_VALIDATOR_STATUS.json",
                    "MMS_FA_STATUS.json",
                ]
                for name in names:
                    gr.JSON(value=_status_file(name), label=name, open=False)
                gr.Markdown(
                    "These status artifacts describe the evidence state of the release. "
                    "A blocked or pending state is preserved rather than replaced with a simulated success."
                )

        gr.Markdown(
            "---\n"
            "**Scientific claim guard:** computational output, synthetic reference runs, protocol text, "
            "calibration metadata and visual glyphs are not by themselves proof of a universal phoneme-to-pattern "
            "or phoneme-to-glyph mapping. Real physical and human-speech claims require the corresponding measurements "
            "and independent controls."
        )
    return demo

# ---------------------------------------------------------------------------
# CPE E2 v7.15 compatibility entry point
# app.ui imports build_research_workbench().
# The workbench implementation is build_app(); expose the research
# workbench under the public name expected by the experimental UI.
# ---------------------------------------------------------------------------

def build_research_workbench():
    return build_app()

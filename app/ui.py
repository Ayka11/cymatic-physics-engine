import base64
import csv
import io
import json
import tempfile
from pathlib import Path

import gradio as gr
import spaces

from .adapter import run_public_demo, REFERENCE_MODAL_TESTS_HZ, generate_modal_test_wav
from .state import PUBLIC_LIMITS
from .workbench import build_research_workbench
from .visualization import (
    audio_overview,
    density_figure,
    spectrum_figure,
    spectrogram_figure,
    stability_figure,
)


def _json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def _report(status):
    pure_tone = status.get("input_mode") == "Pure tone / modal validation"
    grapheme = status.get("grapheme") or (
        "Not applicable - pure-tone mode" if pure_tone else "Not specified"
    )
    phoneme_ipa = status.get("phoneme_ipa") or (
        "Not applicable - pure-tone mode" if pure_tone else "Not specified"
    )
    lines = [
        "# Cymatic Physics Engine — Public Experiment Report",
        "",
        "## 1. Language / alphabet reference",
        f"- Grapheme / letter label: **{grapheme}**",
        f"- Phoneme (IPA): **{phoneme_ipa}**",
        f"- Language / locale: **{status.get('locale', 'not specified')}**",
        f"- Input mode: **{status.get('input_mode', 'not specified')}**",
        "",
        "## 2. Scientific status",
        f"- Status: **{status.get('scientific_status', 'UNKNOWN')}**",
        f"- Experiment ID: `{status.get('experiment_id', 'N/A')}`",
        f"- Audio status: `{status.get('audio_status', 'N/A')}`",
        "",
        "## 3. Acoustic data",
    ]
    ac = status.get("acoustic_metrics", {})
    for k, v in ac.items():
        lines.append(f"- {k}: `{v}`")
    if status.get("generated_test_signal"):
        lines += ["", "### Generated test signal"]
        for k, v in status["generated_test_signal"].items():
            lines.append(f"- {k}: `{v}`")
    lines += ["", "## 4. Model / cymatic data"]
    for section in ("plate_metrics", "pattern_metrics", "stability_metrics"):
        vals = status.get(section, {})
        lines.append(f"### {section.replace('_', ' ').title()}")
        for k, v in vals.items():
            lines.append(f"- {k}: `{v}`")
    lines += ["", "## 5. Provenance"]
    for key in ("config_hash", "content_hash", "provenance_hash", "signature_hash", "audio_profile_hash", "modal_response_hash", "modal_time_series_hash", "source_audio_sha256", "analysis_audio_sha256"):
        if key in status:
            lines.append(f"- {key}: `{status[key]}`")
    lines += [
        "",
        "## 6. Scientific interpretation",
        "The letter/grapheme is an external linguistic label; it is not inferred from the computed pattern.",
        "The public result is a computational reduced-order representation. It is not evidence of a universal phoneme-to-pattern or phoneme-to-glyph mapping.",
        "",
        "## Acoustic input guidance",
        "For clean pattern formation, start with a stable pure tone at one of the reference plate modal frequencies. For speech, use a clean sustained vowel and keep recording conditions consistent.",
        "The recommended audio settings are engineering starting points for this public experiment, not experimentally validated universal constants.",
        "",
        "## Calibration gate",
        "Acoustic/electromechanical transfer calibration CAL-006/007 is required before interpreting the audio spectrum as a measured mechanical force.",
        "",
        "## Full machine-readable status",
        "```json",
        _json(status),
        "```",
    ]
    return "\n".join(lines)


@spaces.GPU(duration=1)
def _zerogpu_probe():
    return None


def _csv_safe(value):
    """Prevent spreadsheet formula execution for untrusted string fields."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _csv_value(value):
    """Convert structured values to deterministic CSV-safe representations."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str
        )
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _csv_bytes(status):
    """Export every status field, recursively preserving nested provenance and metrics."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "experiment_id", "grapheme", "phoneme_ipa",
        "record_group", "field", "value"
    ])
    identity = [
        status.get("experiment_id", ""),
        status.get("grapheme", ""),
        status.get("phoneme_ipa", ""),
    ]

    def emit(group, field, value):
        writer.writerow([
            *map(_csv_safe, identity),
            _csv_safe(str(group)),
            _csv_safe(str(field)),
            _csv_safe(_csv_value(value)),
        ])

    def flatten(group, value, prefix=""):
        if isinstance(value, dict):
            if not value:
                emit(group, prefix or "_value", value)
            else:
                for key, nested in value.items():
                    child = f"{prefix}.{key}" if prefix else str(key)
                    flatten(group, nested, child)
        elif isinstance(value, (list, tuple)):
            emit(group, prefix or "_value", value)
        else:
            emit(group, prefix or "_value", value)

    for key, value in status.items():
        if isinstance(value, dict):
            flatten(key, value)
        elif isinstance(value, (list, tuple)):
            emit(key, "_value", value)
        else:
            emit("experiment_metadata", key, value)

    return output.getvalue().encode("utf-8")



def _generate_tone(frequency_label, duration, amplitude):
    try:
        frequency = REFERENCE_MODAL_TESTS_HZ[frequency_label]
        path, meta = generate_modal_test_wav(frequency, float(duration), float(amplitude))
        return path, _json(meta)
    except Exception as e:
        return None, _json({"status": "FAILED", "error": str(e)})


def _run(wav, duration, particles, grapheme, phoneme_ipa, locale, input_mode, test_frequency_label, tone_amplitude, physical_image, actuator, support_condition, excitation_level, camera_notes, particle_material, repeat_id):
    try:
        test_frequency = REFERENCE_MODAL_TESTS_HZ.get(test_frequency_label) if input_mode == "Pure tone / modal validation" else None
        result, status = run_public_demo(
            wav if input_mode == "Real audio / speech" else None,
            duration, particles,
            grapheme=grapheme or "",
            phoneme_ipa=phoneme_ipa or "",
            locale=locale or "",
            input_mode=input_mode,
            test_frequency_hz=test_frequency,
            tone_amplitude=tone_amplitude,
        )
        status["grapheme"] = grapheme or ""
        status["phoneme_ipa"] = phoneme_ipa or ""
        status["locale"] = locale or ""
        status["input_mode"] = input_mode
        status["physical_measurement"] = {
            "image_uploaded": bool(physical_image),
            "actuator": actuator or "",
            "support_condition": support_condition or "",
            "excitation_level": excitation_level or "",
            "camera_notes": camera_notes or "",
            "particle_material": particle_material or "",
            "repeat_id": repeat_id or "",
            "image_analysis_status": "stored_as_experimental_record_only" if physical_image else "not_supplied",
        }
        if result.get("mode") == "real_audio_reduced_order":
            density = result["density_sequence"][-1]
            spec_fig = spectrum_figure(result["audio_profile"])
            overview_fig = audio_overview(result["audio_profile"])
            spectro_fig = spectrogram_figure(result["audio_profile"])
            stability_fig = stability_figure(result["stability"])
        else:
            density = result["particle_result"].density
            spec_fig = None
            overview_fig = None
            spectro_fig = None
            stability_fig = stability_figure(result["stability"]) if "stability" in result else None

        pattern_fig = density_figure(density, "Cymatic pattern — raw density + deterministic geometry")
        report = _report(status)
        md_path = tempfile.NamedTemporaryFile(prefix="cymatic_report_", suffix=".md", delete=False, mode="w", encoding="utf-8")
        md_path.write(report); md_path.close()
        csv_path = tempfile.NamedTemporaryFile(prefix="cymatic_experiment_", suffix=".csv", delete=False)
        csv_path.write(_csv_bytes(status)); csv_path.close()
        return (_json(status), overview_fig, spectro_fig, pattern_fig, stability_fig,
                spec_fig, report, md_path.name, csv_path.name)
    except Exception as e:
        return (_json({"status": "FAILED", "error": str(e)}), None, None, None, None, None, "", None, None)


def build_app():
    protocol = Path(__file__).resolve().parent.parent / "CPE_PHYSICAL_MEASUREMENT_PROTOCOL_A_Z.md"
    with gr.Blocks(title="Cymatic Physics Engine — Experimental Research Platform") as demo:
        gr.Markdown("# 🌊 Cymatic Physics Engine — Experimental Research Platform")
        gr.Markdown("**From speech to form:** phoneme → acoustic signal → plate response → particle field → stable geometry → candidate glyph.")
        gr.Markdown(
            "**Scientific separation:** Language Layer ≠ Physics Layer. A letter/grapheme is supplied as an external linguistic label; "
            "the engine does not claim that the computed pattern proves the letter's shape."
        )

        gr.Markdown(
            """
### 🧪 CPE E2 v7.15 — Experimental Research Platform

Run the CPE computational experiment directly from the controls below. The primary
workflow is **input → acoustic analysis → plate response → particle field →
stability/geometry → experiment record**. The physical measurement protocol is part of the experimental workflow;
scientific validation remains separate from the computational result.

> **Scientific guard:** a computed result is a reduced-order computational result.
> A physical photograph or user-entered setup metadata is recorded as experimental
> provenance and is not automatically treated as physical validation.
"""
        )

        # ------------------------------------------------------------------
        # Scientific Validation visual panel — intentionally placed before
        # the computational experiment controls so users see the validation
        # context first. These are release/calibration visuals, not claims
        # of completed physical validation.
        # ------------------------------------------------------------------
        validation_assets = Path(__file__).resolve().parent.parent / "assets" / "hfr09"
        validation_atlas = validation_assets / "CPE_HFR09_AZ_CYMATIC_ATLAS.png"
        validation_glyphs = validation_assets / "CPE_HFR09_AZ_UNIQUE_GLYPHS.png"
        validation_calibration = validation_assets / "F1_F2_CALIBRATION.png"

        with gr.Accordion("🔬 CPE E2 v7.15 — Scientific Validation", open=True):
            gr.Markdown(
                """
## Scientific Validation — visual evidence & calibration

These figures are shown **before the experiment controls** to make the scientific
context explicit. They are validation/calibration reference material from the
current release package. They do **not** by themselves establish completed
physical validation of the CPE engine.

**Interpretation:** acoustic input → acoustic parameters → CPE computational
model → reconstructed cymatic field → candidate geometry/glyph. Physical
validation requires the independent measurement and calibration gates described
in the protocol.
"""
            )
            with gr.Row():
                with gr.Column():
                    gr.Image(
                        value=str(validation_calibration),
                        label="Acoustic calibration — F1/F2 reference",
                        interactive=False,
                    )
                with gr.Column():
                    gr.Image(
                        value=str(validation_atlas),
                        label="Cymatic acoustic reconstruction atlas",
                        interactive=False,
                    )
                with gr.Column():
                    gr.Image(
                        value=str(validation_glyphs),
                        label="Unique phonetic glyph atlas",
                        interactive=False,
                    )

            gr.Markdown(
                "**Evidence guard:** visual agreement is exploratory evidence only. "
                "Measured acoustic→mechanical transfer, particle/contact calibration, "
                "repeatability and independent physical validation remain required "
                "before physical interpretation."
            )

        with gr.Row():
            input_mode = gr.Radio(
                choices=["Real audio / speech", "Pure tone / modal validation"],
                value="Real audio / speech",
                label="Experiment input mode",
                info="Use Pure tone first to validate the plate modes before interpreting speech patterns.",
            )

        with gr.Row():
            with gr.Column(scale=2):
                wav = gr.Audio(type="filepath", label="Real audio / phoneme sample (WAV)")
                with gr.Row():
                    grapheme = gr.Textbox(label="Letter / grapheme (reference)", placeholder="A")
                    phoneme_ipa = gr.Textbox(label="Phoneme (IPA)", placeholder="/a/")
                    locale = gr.Dropdown(
                        choices=[
                            ("English — en", "en"), ("Azerbaijani — az", "az"), ("Russian — ru", "ru"), ("Turkish — tr", "tr"),
                            ("German — de", "de"), ("French — fr", "fr"), ("Spanish — es", "es"), ("Italian — it", "it"),
                            ("Portuguese — pt", "pt"), ("Dutch — nl", "nl"), ("Polish — pl", "pl"), ("Ukrainian — uk", "uk"),
                            ("Georgian — ka", "ka"), ("Arabic — ar", "ar"), ("Persian — fa", "fa"), ("Hindi — hi", "hi"),
                            ("Chinese (Mandarin) — zh", "zh"), ("Japanese — ja", "ja"), ("Korean — ko", "ko"), ("Custom / IPA-only", "custom"),
                        ], value="en", label="Language / locale", allow_custom_value=True,
                    )
            with gr.Column(scale=1):
                duration = gr.Number(value=3.0, label="Analysis duration (s)", minimum=0.01, maximum=PUBLIC_LIMITS.max_duration_sec)
                particles = gr.Number(value=10000, label="Particles", minimum=1, maximum=PUBLIC_LIMITS.max_particles, precision=0)

        with gr.Accordion("🎚️ Sound experiment parameters — what makes a pattern clear?", open=True):
            gr.Markdown(
                """
### Recommended starting point

**For the clearest first pattern, use `Pure tone / modal validation`.** A pure sine contains one dominant frequency, so it is much easier to test whether the plate model produces a stable modal structure. Do not try to reproduce the illustrative A–Z image at this stage.

| Parameter | Recommended starting value | Why it matters |
|---|---:|---|
| **Sample rate** | **48 kHz** | Fixed CPE analysis rate; preserves the expected STFT/physics timing. |
| **Channels** | **Mono** | Avoids ambiguity from different left/right signals. |
| **Waveform** | **Sine** for calibration | One controlled frequency is easier to associate with one plate mode. |
| **Frequency** | **53.318 Hz** first, then 133.296, 213.273 Hz… | These are reference modal frequencies for the current 0.30 m × 0.30 m plate model. |
| **Duration** | **3–10 s** for a test tone | Gives the response time to develop and provides repeated frames for stability analysis. |
| **Tone peak amplitude** | **0.25** (normalized digital amplitude) | Conservative computational starting point; this is **not** a physical SPL or force value. |
| **Fade in/out** | **0.5 s** | Reduces an abrupt start/stop transient. |
| **Noise** | **None for calibration** | Noise can obscure the relationship between excitation frequency and pattern. |
| **Speech vowel** | **1–3 s sustained** | For the first phoneme tests, use a steady `/a/`, `/e/`, `/i/`, `/o/`, or `/u/` rather than a short isolated utterance. |
| **Clipping** | **0%** | Clipping introduces nonlinear distortion and extra harmonics. |

**Important:** these are engineering starting values for the public CPE experiment, not universal scientific constants. The current audio→plate path is still a reduced-order prescribed-excitation model; acoustic/electromechanical calibration is required before treating the result as a measured physical response.
                """
            )
            with gr.Row():
                test_frequency = gr.Dropdown(
                    choices=list(REFERENCE_MODAL_TESTS_HZ.keys()),
                    value="f11 — 53.318 Hz",
                    label="Pure-tone / modal test frequency",
                    info="Reference frequencies for the current plate model. Start with f11.",
                )
                tone_amplitude = gr.Number(
                    value=0.25, minimum=0.01, maximum=0.95, step=0.01,
                    label="Pure-tone peak amplitude",
                    info="Normalized digital amplitude, not dB SPL and not mechanical force.",
                )
            generate_tone = gr.Button("Generate Reference Test Tone", variant="secondary")
            tone_preview = gr.Audio(label="Reference tone — listen/check before running", type="filepath", interactive=False)
            tone_info = gr.Code(label="Reference tone parameters", language="json", interactive=False)
            gr.Markdown("**Workflow:** select a CPE reference mode → generate the controlled WAV → listen → run the experiment. This tone is a computational/calibration input, not a measured SPL or force signal.")
            gr.Markdown(
                "**How it works:** select a CPE reference mode → generate the controlled WAV → listen to it → use the generated tone as the input for the experiment. This is a computational/calibration input, not a measured SPL or force signal."
            )

        with gr.Accordion("🎤 How to prepare speech for a clearer phoneme pattern", open=False):
            gr.Markdown(
                """
1. Record **WAV, mono, ideally 48 kHz**. The app can preprocess other supported WAV rates, but 48 kHz is the reference analysis rate.
2. Record in a quiet environment with a stable microphone position.
3. For vowels, sustain the sound for about **1–3 seconds** and use the middle, steady portion of the recording.
4. Avoid clipping; the waveform should not repeatedly hit the digital limits.
5. Avoid MP3/AAC for the research input when possible; uncompressed WAV preserves the original waveform.
6. Keep microphone distance, gain, room and speaking style consistent when comparing phonemes or speakers.
7. For the first phoneme experiment, compare **/a/, /e/, /i/, /o/, /u/** and inspect whether repeated recordings are more similar within a phoneme than between different phonemes.

**Why this matters:** speech contains fundamental frequency, harmonics, formants, transients, amplitude variation and speaker-specific characteristics. A clean sustained vowel makes the first comparison easier, but it does not remove those confounds.
                """
            )

        with gr.Accordion("🧪 Physical experiment setup — protocol checklist", open=True):
            gr.Markdown(
                """
### Purpose
Use this section to prepare a **real physical plate experiment** and keep the physical record connected to the CPE computation. The app does not treat a photograph as proof automatically; it records the measurement metadata and keeps the computational and physical layers separate.

**Quick protocol:**
1. Use the reference plate starting point: **300 × 300 mm, 1 mm steel**.
2. Mount it reproducibly and document the boundary condition.
3. Apply a thin, repeatable particle layer.
4. Start with a controlled sine at one of the CPE reference modal frequencies.
5. Then test sustained speech/letter-name recordings with the same setup.
6. Photograph the final particle pattern from directly above at high resolution.
7. Repeat each target at least 3 times; for research, use multiple utterances and speakers.
8. Keep the original WAV and original photograph unchanged.

**Important:** CPE's current audio→plate path is reduced-order. A physical photograph is stored as an experimental record; it is not automatically declared a validated phoneme glyph.

**Full protocol:** download the `CPE_PHYSICAL_MEASUREMENT_PROTOCOL_A_Z.md` file from the project package, or use the condensed steps above.
                """
            )
            with gr.Row():
                physical_image = gr.Image(type="filepath", label="Physical plate pattern photo (optional)")
                with gr.Column():
                    actuator = gr.Textbox(label="Actuator / excitation method", placeholder="Speaker / shaker / voice coupling")
                    support_condition = gr.Textbox(label="Plate support / boundary condition", placeholder="Simply supported / clamped / other")
                    excitation_level = gr.Textbox(label="Excitation level", placeholder="Amplifier setting / SPL / shaker setting")
            with gr.Row():
                camera_notes = gr.Textbox(label="Camera / imaging notes", placeholder="Top view, distance, resolution, lens")
                particle_material = gr.Textbox(label="Particle material / application", placeholder="Material and approximate layer procedure")
                repeat_id = gr.Textbox(label="Repeat ID", placeholder="A-01, A-02, A-03 …")
            protocol_file = gr.File(value=str(protocol), label="CPE Physical Measurement Protocol A–Z", interactive=False)

        run = gr.Button("▶ Run experiment", variant="primary", size="lg")
        zerogpu_probe = gr.Button(visible=False, elem_id="zerogpu-probe")
        zerogpu_probe.click(_zerogpu_probe, inputs=None, outputs=None, show_progress="hidden")

        with gr.Tab("1 · Acoustic signal"):
            acoustic_overview = gr.Plot(label="Waveform + spectrum")
            spectrogram = gr.Plot(label="Spectrogram")

        with gr.Tab("2 · Cymatic formation"):
            pattern = gr.Plot(label="Raw density + deterministic contour geometry")
            stability = gr.Plot(label="Temporal stability")

        with gr.Tab("3 · Experiment data"):
            status = gr.Code(label="Machine-readable status / provenance", language="json")
            report = gr.Markdown(label="Scientific report")
            with gr.Row():
                report_file = gr.File(label="Download Markdown report")
                csv_file = gr.File(label="Download experiment data CSV")

        with gr.Accordion("Reference spectrum", open=False):
            spectrum = gr.Plot(label="Input spectrum")

        generate_tone.click(
            _generate_tone,
            inputs=[test_frequency, duration, tone_amplitude],
            outputs=[tone_preview, tone_info],
        )
        run.click(
            _run,
            inputs=[wav, duration, particles, grapheme, phoneme_ipa, locale, input_mode, test_frequency, tone_amplitude, physical_image, actuator, support_condition, excitation_level, camera_notes, particle_material, repeat_id],
            outputs=[status, acoustic_overview, spectrogram, pattern, stability, spectrum, report, report_file, csv_file],
        )

        gr.Markdown(
            "### Evidence guard\n"
            "**A successful computation is not a physical validation.** CAL-006/007 acoustic-to-force calibration, particle/contact calibration, and experimental PV0–PV5 validation remain prerequisites for measured physical interpretation.\n\n"
            "### Public limits\n"
            f"Max duration: {PUBLIC_LIMITS.max_duration_sec:g} s · Max particles: {PUBLIC_LIMITS.max_particles:,} · Reference modes: 16×16 · Reference grid: 256×256."
        )

        with gr.Tab("4 · Physical Experiment Protocol"):
            gr.Markdown("## CPE Physical Measurement Protocol")
            gr.Markdown(
                """
### Purpose
Use this protocol when collecting **real physical plate measurements**. The computational result and the physical observation remain separate until the required calibration and validation gates are satisfied.

### Quick protocol
1. Reference plate: **300 × 300 mm, 1 mm steel**.
2. Mount reproducibly and document the boundary condition.
3. Apply a thin, repeatable particle layer.
4. Start with a controlled sine at a CPE reference modal frequency.
5. Then test sustained speech/letter-name recordings using the same setup.
6. Photograph the final particle pattern from directly above.
7. Repeat each target at least 3 times; research studies should use multiple utterances and speakers.
8. Preserve the original WAV and original photograph unchanged.

**Important:** a letter is a linguistic label, not a physical shape. A photograph is stored as an experimental record and is not automatically declared a validated phoneme/glyph.
                """
            )
            gr.File(value=str(protocol), label="Download full physical measurement protocol", interactive=False)

        with gr.Tab("5 · Scientific Validation"):
            gr.Markdown(
                """
## Scientific validation status

This section exposes the release evidence gates. **BLOCKED/PENDING is a valid fail-closed state** and means the required real evidence has not yet been supplied.

**Pipeline:** REAL MMS-FA → explicit Character→Phone projection → candidate QC → 680-candidate dataset → speaker balance → reproducibility → final benchmark → scientific validation.

HFR-09 visual/calibration material is intentionally not part of the public experimental workflow.
                """
            )
            release_status = {}
            for label, filename in [
                ("MMS-FA", "MMS_FA_STATUS.json"),
                ("Alignment Validator v7.04", "ALIGNMENT_VALIDATOR_STATUS.json"),
                ("Candidate QC v7.05", "CANDIDATE_QC_STATUS.json"),
                ("680 Dataset Builder v7.06", "DATASET_BUILDER_STATUS.json"),
                ("Corpus/Speaker QC v7.07", "CORPUS_BALANCE_QC_STATUS.json"),
                ("Reproducibility v7.08", "REPRODUCIBILITY_MANIFEST_v708.json"),
                ("Final Benchmark v7.09", "V7_09_STATUS.json"),
                ("Real Corpus Run v7.13", "REAL_CORPUS_RUN_v713_STATUS.json"),
                ("Scientific Validation v7.14", "SCIENTIFIC_VALIDATION_v714_STATUS.json"),
            ]:
                p = Path(__file__).resolve().parent.parent / "results" / filename
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except Exception as exc:
                    data = {"status": "UNAVAILABLE", "error": str(exc)}
                release_status[label] = data.get("status", "UNKNOWN")
            gr.JSON(value=release_status, label="Scientific gate status", open=False)

        with gr.Tab("6 · Scientific Research Workbench"):
            gr.Markdown(
                """
## Full Experimental Research Workbench

Use this area for **measurement analysis, calibration records, physical-validation evaluation, and reproducibility**. It is intentionally separated from the quick experiment interface above.

**Suggested order:** Measurement Analysis → Calibration → Physical Validation → Physical Experiment Protocol → Analysis & Reproducibility.
                """
            )
            build_research_workbench()

    return demo

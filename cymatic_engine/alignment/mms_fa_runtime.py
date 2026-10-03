from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any

import torch
import torchaudio

MMS_MODEL_ID = "torchaudio.pipelines.MMS_FA"
MMS_SAMPLE_RATE = 16000


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_mms_text(text: str) -> str:
    """Strict MMS_FA-compatible romanized text normalization.

    MMS_FA's tokenizer is character based. Hyphen is the CTC blank token in the
    published dictionary and must not be passed as transcript content.
    """
    text = text.lower().replace("’", "'").replace("`", "'")
    text = re.sub(r"[^a-z' ]", " ", text)
    return re.sub(r" +", " ", text).strip()


def load_audio_16k(path: str | Path):
    """Load audio through soundfile, then resample to the MMS_FA rate."""
    import soundfile as sf

    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    waveform = torch.from_numpy(audio.T.copy())

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sr != MMS_SAMPLE_RATE:
        waveform = torchaudio.functional.resample(
            waveform, orig_freq=sr, new_freq=MMS_SAMPLE_RATE
        )
        sr = MMS_SAMPLE_RATE

    if waveform.ndim != 2 or waveform.shape[0] != 1:
        raise ValueError(
            f"Expected mono [1, samples] waveform, got {tuple(waveform.shape)}"
        )
    if waveform.shape[-1] == 0:
        raise ValueError("Audio file contains no samples")

    return waveform.contiguous(), sr


class MMSFARuntime:
    def __init__(self, device: str = "auto", with_star: bool = False):
        self.bundle = torchaudio.pipelines.MMS_FA
        self.device = torch.device(
            "cuda" if device == "auto" and torch.cuda.is_available() else
            "cpu" if device == "auto" else device
        )
        self.with_star = with_star
        self.model = None
        self.tokenizer = self.bundle.get_tokenizer()
        self.aligner = self.bundle.get_aligner()
        self.dictionary = self.bundle.get_dict()
        self.reverse_dictionary = {v: k for k, v in self.dictionary.items()}

    def load(self):
        self.model = self.bundle.get_model(with_star=self.with_star).to(self.device)
        self.model.eval()
        return self

    def align(self, audio_path: str | Path, transcript: str) -> dict[str, Any]:
        if self.model is None:
            self.load()
        original = transcript
        normalized = normalize_mms_text(transcript)
        if not normalized:
            raise ValueError("normalized transcript is empty")

        waveform, sample_rate = load_audio_16k(audio_path)
        waveform = waveform.to(self.device)
        words = normalized.split()
        tokens = self.tokenizer(words)
        with torch.inference_mode():
            emission, _ = self.model(waveform)
        emission = emission[0].cpu()
        spans_by_word = self.aligner(emission, tokens)

        nframes = int(emission.shape[0])
        nsamples = int(waveform.shape[-1])
        frame_scale = nsamples / float(nframes)
        records = []
        char_cursor = 0
        for word_index, (word, spans) in enumerate(zip(words, spans_by_word)):
            word_char_start = normalized.find(word, char_cursor)
            word_char_end = word_char_start + len(word)
            char_cursor = word_char_end + 1
            for char_index, span in enumerate(spans):
                raw = self.reverse_dictionary[int(span.token)]
                start_sample = max(0, min(nsamples, int(round(span.start * frame_scale))))
                end_sample = max(0, min(nsamples, int(round(span.end * frame_scale))))
                records.append({
                    "word_index": word_index,
                    "char_index": char_index,
                    "char": raw,
                    "char_start": word_char_start + char_index,
                    "char_end": word_char_start + char_index + 1,
                    "start_frame": int(span.start),
                    "end_frame": int(span.end),
                    "start_sample": start_sample,
                    "end_sample": end_sample,
                    "confidence": float(span.score),
                })

        return {
            "status": "PASS",
            "model_id": MMS_MODEL_ID,
            "model_version": "MMS_FA",
            "sample_rate": sample_rate,
            "audio_samples": nsamples,
            "emission_frames": nframes,
            "audio_sha256": sha256_file(audio_path),
            "transcript_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
            "transcript_raw": original,
            "transcript_normalized": normalized,
            "records": records,
            "device": str(self.device),
        }


def phone_projection_gate(alignment: dict[str, Any], phone_records: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Explicit gate: MMS_FA character spans are not phoneme spans.

    A 34-phone dataset may only proceed when a separately documented phone-level
    projection is supplied. This prevents silently treating graphemes as phones.
    """
    if not phone_records:
        return {
            "status": "BLOCKED",
            "reason": "PHONE_PROJECTION_REQUIRED",
            "detail": "MMS_FA produces character/token alignment; a 34-phone output requires an explicit phone projection layer.",
        }
    required = {"phone", "start_sample", "end_sample", "source_char_start", "source_char_end"}
    missing = sorted(required - set(phone_records[0])) if phone_records else sorted(required)
    if missing:
        return {"status": "BLOCKED", "reason": "PHONE_PROJECTION_SCHEMA", "missing": missing}
    return {"status": "PASS", "count": len(phone_records)}

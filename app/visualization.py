import matplotlib.pyplot as plt
import numpy as np


def _db(mag, floor=1e-12):
    x = np.asarray(mag, dtype=float)
    ref = max(float(np.max(x)), floor)
    return 20.0 * np.log10(np.maximum(x, floor) / ref)


def audio_overview(profile, max_hz=12000):
    """Standard, measured-input acoustic visualization: waveform + spectrum."""
    fig = plt.figure(figsize=(10, 5.8))
    ax1 = fig.add_subplot(2, 1, 1)
    x = np.asarray(profile.samples)
    t = np.arange(len(x), dtype=float) / float(profile.sample_rate_hz)
    ax1.plot(t, x, linewidth=0.7)
    ax1.set_title("1. Acoustic waveform — real input")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")
    ax1.grid(alpha=0.15)

    ax2 = fig.add_subplot(2, 1, 2)
    mag = np.asarray(profile.magnitude)
    if mag.ndim == 2:
        mag = np.mean(mag, axis=1)
    f = np.asarray(profile.frequency_hz)
    mask = f <= min(max_hz, f[-1] if len(f) else max_hz)
    ax2.plot(f[mask], _db(mag[mask]), linewidth=0.9)
    ax2.set_title("2. Acoustic spectrum")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Magnitude (dB, relative)")
    ax2.set_xlim(0, max_hz)
    ax2.grid(alpha=0.15)
    fig.tight_layout()
    return fig


def spectrogram_figure(profile, max_hz=12000):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    Z = np.asarray(profile.magnitude)
    if Z.ndim == 2:
        Z = np.maximum(Z, 1e-12)
    f = np.asarray(profile.frequency_hz)
    t = np.asarray(profile.time_sec)
    mask = f <= min(max_hz, f[-1] if len(f) else max_hz)
    Zdb = _db(Z[mask, :])
    im = ax.pcolormesh(t, f[mask], Zdb, shading="auto")
    ax.set_title("3. Spectrogram — time/frequency structure")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    fig.colorbar(im, ax=ax, label="Relative magnitude (dB)")
    fig.tight_layout()
    return fig


def density_figure(density, title="Computed cymatic pattern"):
    """Raw density plus deterministic contour geometry; no smoothing or beautification."""
    d = np.asarray(density, dtype=float)
    fig = plt.figure(figsize=(10, 4.8))
    ax1 = fig.add_subplot(1, 2, 1)
    im = ax1.imshow(d, origin="lower", interpolation="nearest")
    ax1.set_title("4. Raw particle density")
    ax1.set_xlabel("x grid")
    ax1.set_ylabel("y grid")
    fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)

    ax2 = fig.add_subplot(1, 2, 2)
    dpos = np.maximum(d, 0)
    vmax = float(np.max(dpos)) if dpos.size else 0.0
    if vmax > 0:
        levels = [0.10, 0.25, 0.50, 0.75, 0.90]
        ax2.contour(dpos / vmax, levels=levels)
    ax2.set_aspect("equal")
    ax2.set_title("5. Deterministic contour geometry")
    ax2.set_xlabel("x grid")
    ax2.set_ylabel("y grid")
    ax2.text(0.02, 0.02, "No smoothing / topology-changing fitting", transform=ax2.transAxes, fontsize=8)
    fig.suptitle(title)
    fig.tight_layout()
    return fig


def plate_pattern_figure(plate_sequence):
    """Show the physical/model plate field and the final particle density separately."""
    disp = np.asarray(plate_sequence.displacement)
    field = disp[-1] if disp.size else np.zeros((2, 2))
    fig, ax = plt.subplots(figsize=(5.2, 4.8))
    im = ax.imshow(field, origin="lower", extent=[0, 1, 0, 1], interpolation="nearest")
    ax.set_title("Plate displacement field — final sampled frame")
    ax.set_xlabel("normalized x")
    ax.set_ylabel("normalized y")
    fig.colorbar(im, ax=ax, label="Displacement (model units)")
    fig.tight_layout()
    return fig


def stability_figure(stability):
    fig = plt.figure(figsize=(10, 4.2))
    ax1 = fig.add_subplot(1, 2, 1)
    D = np.asarray(stability.frame_distance)
    C = np.asarray(stability.correlation)
    ax1.plot(np.arange(1, len(D) + 1), D, label="Frame distance")
    ax1.plot(np.arange(1, len(C) + 1), 1.0 - C, label="1 − correlation")
    ax1.set_title("6. Pattern temporal change")
    ax1.set_xlabel("Frame")
    ax1.set_ylabel("Metric")
    ax1.legend()
    ax1.grid(alpha=0.15)

    ax2 = fig.add_subplot(1, 2, 2)
    H = np.asarray(stability.entropy_normalized)
    ax2.plot(np.arange(len(H)), H)
    ax2.set_title(f"Stability state: {stability.state}")
    ax2.set_xlabel("Frame")
    ax2.set_ylabel("Normalized density entropy")
    ax2.grid(alpha=0.15)
    fig.tight_layout()
    return fig


def spectrum_figure(profile):
    # Backward-compatible compact spectrum.
    fig, ax = plt.subplots(figsize=(7, 3.5))
    mag = np.asarray(profile.magnitude)
    if mag.ndim == 2:
        mag = np.mean(mag, axis=1)
    f = np.asarray(profile.frequency_hz)
    mask = f <= 12000
    ax.plot(f[mask], _db(mag[mask]))
    ax.set_xlim(0, 12000)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB, relative)")
    ax.set_title("Input spectrum")
    fig.tight_layout()
    return fig

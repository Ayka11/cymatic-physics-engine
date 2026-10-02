from dataclasses import dataclass

@dataclass(frozen=True)
class AcquisitionConfig:
    sample_rate_hz: int = 48000
    bits: int = 24
    anti_alias_filter: bool = True
    force_sensor_required: bool = True
    accelerometer_required: bool = True
    synchronized_channels: bool = True

def validate_acquisition(config: AcquisitionConfig) -> list[str]:
    warnings = []
    if config.sample_rate_hz < 48000:
        warnings.append("Sample rate below the reference 48 kHz protocol.")
    if config.bits < 24:
        warnings.append("ADC resolution below the reference 24-bit protocol.")
    if not config.anti_alias_filter:
        warnings.append("Anti-alias filtering is disabled.")
    if config.force_sensor_required is False:
        warnings.append("Force calibration is unavailable; PV5 cannot be claimed.")
    if not config.synchronized_channels:
        warnings.append("Unsynchronized channels invalidate phase-sensitive comparison.")
    return warnings

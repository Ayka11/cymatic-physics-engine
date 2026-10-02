# CPE E2 v7.15 — FULL PLATFORM RESTORED
# Hugging Face ZeroGPU-compatible launcher.
import spaces
import gradio as gr
from app.ui import build_app

@spaces.GPU(duration=10)
def zerogpu_self_test():
    """Minimal CUDA health check; does not alter scientific results."""
    import torch
    if not torch.cuda.is_available():
        return "GPU unavailable inside ZeroGPU allocation."
    x = torch.tensor([1.0, 2.0, 3.0], device="cuda")
    y = torch.sum(x * x).item()
    return f"ZeroGPU self-test PASS — device: {torch.cuda.get_device_name(0)}; tensor sum-of-squares: {y:.1f}"

demo = build_app()

if __name__ == "__main__":
    demo.launch()

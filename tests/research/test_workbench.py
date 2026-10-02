import gradio as gr

from app.research.workbench import build_research_workbench


def build_research_test_app():
    with gr.Blocks() as demo:
        with gr.Tab("Scientific Research"):
            build_research_workbench()
    return demo


def test_research_workbench_builds():
    demo = build_research_test_app()
    assert isinstance(demo, gr.Blocks)

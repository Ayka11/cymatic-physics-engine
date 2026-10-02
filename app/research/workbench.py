import gradio as gr

from .integration import get_research_status


def build_research_workbench():
    with gr.Column():
        gr.Markdown(
            """
# Scientific Research Workbench

CPE v7.15 scientific evidence and reproducibility control panel.

The workbench is fail-closed: missing real evidence remains BLOCKED.
"""
        )

        refresh_btn = gr.Button("Refresh Scientific Status")

        status_table = gr.Dataframe(
            headers=["Gate", "Status", "Detail"],
            datatype=["str", "str", "str"],
            value=[
                [item.name, item.status, item.detail]
                for item in get_research_status()
            ],
            interactive=False,
            row_count=(7, "dynamic"),
        )

        refresh_btn.click(
            fn=lambda: [
                [item.name, item.status, item.detail]
                for item in get_research_status()
            ],
            inputs=None,
            outputs=status_table,
        )

    return status_table

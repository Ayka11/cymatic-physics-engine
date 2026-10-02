from pathlib import Path

from app.research.integration import (
    ScientificResearchController,
    get_research_status,
)


def test_research_controller_is_fail_closed():
    controller = ScientificResearchController(Path.cwd())
    statuses = controller.get_status()

    assert statuses
    assert any(item.status == "BLOCKED" for item in statuses)


def test_research_status_is_deterministic():
    first = [
        (x.name, x.status, x.detail)
        for x in get_research_status(Path.cwd())
    ]
    second = [
        (x.name, x.status, x.detail)
        for x in get_research_status(Path.cwd())
    ]

    assert first == second

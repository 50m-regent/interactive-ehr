"""Clinical task reference model tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from interactive_ehr.evaluation import (
    ClinicalTaskGraph,
    ReferenceStatus,
    audit_information_trace,
    load_clinical_task_graph,
)
from interactive_ehr.scenario_graph import parse_scenario_graph_json


REFERENCE_PATH = Path("data/evaluation/ito_clinical_tasks.v1.json")


def test_load_ito_clinical_task_reference() -> None:
    """Load the seven clinical tasks captured in the interview notes."""

    graph = load_clinical_task_graph(REFERENCE_PATH)

    assert graph.status is ReferenceStatus.DRAFT
    assert [task.id for task in graph.tasks] == [
        "T1",
        "T2",
        "T3",
        "T4",
        "T5",
        "T6",
        "T7",
    ]
    assert graph.tasks[5].depends_on == ["T4"]
    assert graph.tasks[6].depends_on == ["T1", "T2", "T3", "T4", "T5", "T6"]


def test_clinical_task_graph_rejects_unknown_dependency() -> None:
    """Reject dependencies that do not point to another clinical task."""

    with pytest.raises(ValidationError, match="unknown dependencies"):
        ClinicalTaskGraph.model_validate(
            {
                "id": "invalid",
                "version": "1",
                "title": "invalid",
                "actor": "doctor",
                "context": "test",
                "status": "draft",
                "source": "test",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "task",
                        "order": 1,
                        "depends_on": ["missing"],
                    }
                ],
            }
        )


def test_audit_information_trace_identifies_current_gaps() -> None:
    """Report source requirements that have no runtime DataNode trace."""

    graph = load_clinical_task_graph(REFERENCE_PATH)
    scenario = parse_scenario_graph_json(
        Path("data/scenarios/ito.json").read_text(encoding="utf-8")
    )

    audit = audit_information_trace(
        graph,
        known_data_node_ids={node.id for node in scenario.data_nodes},
        known_widget_ids={node.id for node in scenario.widget_nodes},
    )

    assert audit.required_source_count == 16
    assert audit.traced_source_count == 11
    assert audit.trace_rate == 0.6875
    assert audit.missing_requirement_keys == [
        "T1.measurement_date",
        "T5.ecg",
        "T5.chest_xray",
        "T5.pulmonary_function",
        "T6.anesthesia_complications",
    ]
    assert audit.tasks_without_runtime_widgets == ["T7"]
    assert audit.unknown_runtime_data_node_ids == []
    assert audit.unknown_runtime_widget_ids == []

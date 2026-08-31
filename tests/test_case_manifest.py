"""Synthetic evaluation case manifest tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from interactive_ehr.evaluation import (
    CaseReviewStatus,
    EvaluationCaseManifest,
    ReferenceStatus,
    audit_case_manifest,
    load_clinical_task_graph,
    load_evaluation_case_manifest,
)


MANIFEST_PATH = Path("data/evaluation/ito_case_manifest.v0.1.json")
TASK_GRAPH_PATH = Path("data/evaluation/ito_clinical_tasks.v1.json")


def test_draft_manifest_is_blocked_from_pilot() -> None:
    """Block cases until expert review, scoring, complexity, and UI are ready."""

    manifest = load_evaluation_case_manifest(MANIFEST_PATH)
    task_graph = load_clinical_task_graph(TASK_GRAPH_PATH)

    audit = audit_case_manifest(manifest, task_graph)

    assert [case.id for case in manifest.cases] == ["ITO-CASE-A", "ITO-CASE-B"]
    assert all(case.review_status is CaseReviewStatus.DRAFT for case in manifest.cases)
    assert audit.ready_for_pilot is False
    assert audit.clinical_task_graph_not_expert_reviewed is True
    assert audit.cases_not_expert_reviewed == ["ITO-CASE-A", "ITO-CASE-B"]
    assert audit.cases_without_scenario_graph == ["ITO-CASE-A", "ITO-CASE-B"]
    assert audit.questions_without_scoring == ["ITO-CASE-A.Q1", "ITO-CASE-B.Q1"]
    assert audit.cases_with_incomplete_complexity == ["ITO-CASE-A", "ITO-CASE-B"]
    assert audit.unknown_clinical_task_ids == []
    assert audit.unknown_requirement_keys == []


def test_complete_expert_reviewed_manifest_is_ready() -> None:
    """Accept a complete manifest whose references match the clinical task graph."""

    payload = load_evaluation_case_manifest(MANIFEST_PATH).model_dump(mode="json")
    for case in payload["cases"]:
        case["scenario_graph_path"] = "data/scenarios/ito.json"
        case["review_status"] = "expert-reviewed"
        case["complexity"] = {
            "required_information_count": 16,
            "abnormal_finding_count": 2,
            "safety_critical_finding_count": 1,
            "active_conditional_task_count": 1,
            "source_system_count": 3,
        }
        case["questions"][0]["scoring_criteria"] = [
            {
                "id": "C1",
                "description": "必要な患者基本情報を確認できる",
                "clinical_task_id": "T1",
                "requirement_keys": ["T1.demographics"],
                "severity": "standard",
                "points": 1,
            }
        ]
    manifest = EvaluationCaseManifest.model_validate(payload)
    task_graph = load_clinical_task_graph(TASK_GRAPH_PATH).model_copy(
        update={"status": ReferenceStatus.EXPERT_REVIEWED}
    )

    audit = audit_case_manifest(manifest, task_graph)

    assert audit.ready_for_pilot is True
    assert audit.reasons == []


def test_manifest_rejects_same_patient_in_a_pair() -> None:
    """Reject matched cases that reuse the same synthetic patient."""

    payload = load_evaluation_case_manifest(MANIFEST_PATH).model_dump(mode="json")
    payload["cases"][1]["synthetic_patient_id"] = payload["cases"][0][
        "synthetic_patient_id"
    ]

    with pytest.raises(ValidationError, match="distinct patients"):
        EvaluationCaseManifest.model_validate(payload)


def test_manifest_rejects_unknown_case_in_a_pair() -> None:
    """Reject pair references that do not identify a declared case."""

    payload = load_evaluation_case_manifest(MANIFEST_PATH).model_dump(mode="json")
    payload["pairs"][0]["case_ids"][1] = "UNKNOWN"

    with pytest.raises(ValidationError, match="unknown cases"):
        EvaluationCaseManifest.model_validate(payload)

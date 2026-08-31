"""Models and readiness checks for matched synthetic evaluation cases."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from interactive_ehr.evaluation.task_model import ClinicalTaskGraph, ReferenceStatus


class CaseReviewStatus(str, Enum):
    """Expert review status of a synthetic evaluation case."""

    DRAFT = "draft"
    EXPERT_REVIEWED = "expert-reviewed"


class ScoringSeverity(str, Enum):
    """Clinical importance assigned to one scoring criterion."""

    STANDARD = "standard"
    CRITICAL = "critical"


class ScoringCriterion(BaseModel):
    """One observable element used to score an evaluation response."""

    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    clinical_task_id: str
    requirement_keys: list[str] = Field(default_factory=list)
    severity: ScoringSeverity = ScoringSeverity.STANDARD
    points: float = Field(gt=0)


class EvaluationQuestion(BaseModel):
    """A question answered by a participant using the assigned interface."""

    model_config = ConfigDict(frozen=True)

    id: str
    prompt: str
    clinical_task_ids: list[str] = Field(min_length=1)
    response_type: Literal["free-text", "multi-select", "structured"]
    scoring_criteria: list[ScoringCriterion] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scoring_task_links(self) -> Self:
        """Ensure criterion IDs are unique and refer to a question task."""

        criterion_ids = [criterion.id for criterion in self.scoring_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError(f"scoring criterion IDs must be unique: {self.id}")
        question_task_ids = set(self.clinical_task_ids)
        for criterion in self.scoring_criteria:
            if criterion.clinical_task_id not in question_task_ids:
                raise ValueError(
                    f"criterion task must be linked by question {self.id}: "
                    f"{criterion.clinical_task_id}"
                )
        return self


class CaseComplexityProfile(BaseModel):
    """Predefined dimensions used to compare the difficulty of two cases."""

    model_config = ConfigDict(frozen=True)

    required_information_count: int | None = Field(None, ge=0)
    abnormal_finding_count: int | None = Field(None, ge=0)
    safety_critical_finding_count: int | None = Field(None, ge=0)
    active_conditional_task_count: int | None = Field(None, ge=0)
    source_system_count: int | None = Field(None, ge=0)

    def is_complete(self) -> bool:
        """Return whether every prespecified difficulty dimension is recorded."""

        return all(value is not None for value in self.model_dump().values())


class EvaluationCase(BaseModel):
    """A synthetic case, its questions, and its review metadata."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    synthetic_patient_id: str
    scenario_graph_path: str | None = None
    review_status: CaseReviewStatus = CaseReviewStatus.DRAFT
    questions: list[EvaluationQuestion] = Field(min_length=1)
    complexity: CaseComplexityProfile

    @model_validator(mode="after")
    def validate_question_ids(self) -> Self:
        """Ensure question IDs are unique within the case."""

        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError(f"question IDs must be unique: {self.id}")
        return self


class MatchedCasePair(BaseModel):
    """Two distinct synthetic cases assigned in a counterbalanced study."""

    model_config = ConfigDict(frozen=True)

    id: str
    case_ids: tuple[str, str]

    @model_validator(mode="after")
    def validate_distinct_cases(self) -> Self:
        """Reject a pair that repeats the same case."""

        if self.case_ids[0] == self.case_ids[1]:
            raise ValueError(f"matched pair must contain distinct cases: {self.id}")
        return self


class EvaluationCaseManifest(BaseModel):
    """Versioned collection of synthetic cases and matched pairs."""

    model_config = ConfigDict(frozen=True)

    id: str
    version: str
    clinical_task_graph_id: str
    cases: list[EvaluationCase] = Field(min_length=2)
    pairs: list[MatchedCasePair] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_case_references(self) -> Self:
        """Ensure IDs are unique and every pair refers to distinct patients."""

        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case IDs must be unique")
        pair_ids = [pair.id for pair in self.pairs]
        if len(pair_ids) != len(set(pair_ids)):
            raise ValueError("matched pair IDs must be unique")

        cases_by_id = {case.id: case for case in self.cases}
        for pair in self.pairs:
            unknown_case_ids = set(pair.case_ids) - cases_by_id.keys()
            if unknown_case_ids:
                unknown = ", ".join(sorted(unknown_case_ids))
                raise ValueError(f"unknown cases for {pair.id}: {unknown}")
            patient_ids = {
                cases_by_id[case_id].synthetic_patient_id for case_id in pair.case_ids
            }
            if len(patient_ids) != 2:
                raise ValueError(f"matched pair must use distinct patients: {pair.id}")
        return self


class CaseManifestReadinessAudit(BaseModel):
    """Reasons a case manifest is or is not ready for a participant pilot."""

    model_config = ConfigDict(frozen=True)

    ready_for_pilot: bool
    reasons: list[str]
    clinical_task_graph_not_expert_reviewed: bool
    cases_not_expert_reviewed: list[str]
    cases_without_scenario_graph: list[str]
    questions_without_scoring: list[str]
    cases_with_incomplete_complexity: list[str]
    unknown_clinical_task_ids: list[str]
    unknown_requirement_keys: list[str]


def load_evaluation_case_manifest(path: Path) -> EvaluationCaseManifest:
    """Load and validate an evaluation case manifest JSON file."""

    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    return EvaluationCaseManifest.model_validate(payload)


def audit_case_manifest(
    manifest: EvaluationCaseManifest,
    clinical_task_graph: ClinicalTaskGraph,
    *,
    project_root: Path | None = None,
) -> CaseManifestReadinessAudit:
    """Check expert review, scoring, complexity, and task traceability gates."""

    root = project_root or Path.cwd()
    known_task_ids = {task.id for task in clinical_task_graph.tasks}
    known_requirement_keys = {
        f"{task.id}.{requirement.id}"
        for task in clinical_task_graph.tasks
        for requirement in task.information_requirements
    }
    referenced_task_ids = {
        task_id
        for case in manifest.cases
        for question in case.questions
        for task_id in question.clinical_task_ids
    } | {
        criterion.clinical_task_id
        for case in manifest.cases
        for question in case.questions
        for criterion in question.scoring_criteria
    }
    referenced_requirement_keys = {
        requirement_key
        for case in manifest.cases
        for question in case.questions
        for criterion in question.scoring_criteria
        for requirement_key in criterion.requirement_keys
    }
    cases_not_reviewed = sorted(
        case.id
        for case in manifest.cases
        if case.review_status is not CaseReviewStatus.EXPERT_REVIEWED
    )
    cases_without_scenario = sorted(
        case.id
        for case in manifest.cases
        if not case.scenario_graph_path
        or not (root / case.scenario_graph_path).is_file()
    )
    questions_without_scoring = sorted(
        f"{case.id}.{question.id}"
        for case in manifest.cases
        for question in case.questions
        if not question.scoring_criteria
    )
    cases_with_incomplete_complexity = sorted(
        case.id for case in manifest.cases if not case.complexity.is_complete()
    )
    unknown_task_ids = sorted(referenced_task_ids - known_task_ids)
    unknown_requirement_keys = sorted(
        referenced_requirement_keys - known_requirement_keys
    )
    gate_results = {
        "clinical task graph requires expert review": (
            clinical_task_graph.status is not ReferenceStatus.EXPERT_REVIEWED
        ),
        "clinical task graph ID does not match": (
            manifest.clinical_task_graph_id != clinical_task_graph.id
        ),
        "cases require expert review": bool(cases_not_reviewed),
        "cases require a ScenarioGraph": bool(cases_without_scenario),
        "questions require scoring criteria": bool(questions_without_scoring),
        "case complexity profiles are incomplete": bool(
            cases_with_incomplete_complexity
        ),
        "unknown clinical task IDs are referenced": bool(unknown_task_ids),
        "unknown information requirement keys are referenced": bool(
            unknown_requirement_keys
        ),
    }
    reasons = [reason for reason, failed in gate_results.items() if failed]
    return CaseManifestReadinessAudit(
        ready_for_pilot=not reasons,
        reasons=reasons,
        clinical_task_graph_not_expert_reviewed=(
            clinical_task_graph.status is not ReferenceStatus.EXPERT_REVIEWED
        ),
        cases_not_expert_reviewed=cases_not_reviewed,
        cases_without_scenario_graph=cases_without_scenario,
        questions_without_scoring=questions_without_scoring,
        cases_with_incomplete_complexity=cases_with_incomplete_complexity,
        unknown_clinical_task_ids=unknown_task_ids,
        unknown_requirement_keys=unknown_requirement_keys,
    )

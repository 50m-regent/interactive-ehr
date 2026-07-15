"""Clinical task reference models kept separate from runtime UI views."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReferenceStatus(str, Enum):
    """Review status of a clinical task reference model."""

    DRAFT = "draft"
    EXPERT_REVIEWED = "expert-reviewed"


class InformationRequirement(BaseModel):
    """Information required to complete one clinical task."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="タスク内で一意な情報要件ID")
    label: str = Field(description="医療従事者が確認する情報")
    kind: Literal["source", "derived"] = Field(
        "source",
        description="EHRから取得する情報か、確認後に作る判断結果か",
    )
    required: bool = Field(True, description="タスク完了に必須か")
    source_systems: list[str] = Field(
        default_factory=list,
        description="現在のEHRで情報が存在する画面または部門システム",
    )
    time_window: str | None = Field(None, description="情報の期間または鮮度条件")
    rationale: str | None = Field(None, description="この情報が必要な理由")
    runtime_data_node_ids: list[str] = Field(
        default_factory=list,
        description="現在のScenarioGraphで対応するDataNode ID",
    )


class ClinicalTaskNode(BaseModel):
    """A clinical information-processing task independent from UI layout."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="診療タスクID")
    title: str = Field(description="診療タスク名")
    description: str = Field(description="確認、判断、入力する内容")
    order: int = Field(description="診療フロー上のおおよその順序")
    depends_on: list[str] = Field(
        default_factory=list,
        description="開始前に完了している必要がある診療タスクID",
    )
    condition: str | None = Field(None, description="条件付きタスクの実施条件")
    completion_criteria: list[str] = Field(
        default_factory=list,
        description="タスクを完了したと判定する基準",
    )
    information_requirements: list[InformationRequirement] = Field(
        default_factory=list,
        description="タスク完了に必要な情報",
    )
    runtime_task_ids: list[str] = Field(
        default_factory=list,
        description="現在のScenarioGraphで対応するTaskNode ID",
    )
    runtime_widget_ids: list[str] = Field(
        default_factory=list,
        description="現在のScenarioGraphで対応するWidgetNode ID",
    )

    @model_validator(mode="after")
    def validate_requirement_ids(self) -> Self:
        """Ensure requirement IDs are unique within the task."""

        requirement_ids = [item.id for item in self.information_requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError(f"information requirement IDs must be unique: {self.id}")
        return self


class ClinicalTaskGraph(BaseModel):
    """A reviewable clinical task model used as an evaluation reference."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="臨床タスクモデルID")
    version: str = Field(description="モデルの版")
    title: str = Field(description="診療シナリオ名")
    actor: str = Field(description="タスクを実施する利用者")
    context: str = Field(description="診療場面と目的")
    status: ReferenceStatus = Field(description="専門家確認の状態")
    source: str = Field(description="モデル作成に用いた資料")
    scenario_completion_criteria: list[str] = Field(default_factory=list)
    tasks: list[ClinicalTaskNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_task_graph(self) -> Self:
        """Ensure task IDs and dependency references form a valid graph."""

        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("clinical task IDs must be unique")

        known_ids = set(task_ids)
        for task in self.tasks:
            unknown_dependencies = set(task.depends_on) - known_ids
            if unknown_dependencies:
                unknown = ", ".join(sorted(unknown_dependencies))
                raise ValueError(f"unknown dependencies for {task.id}: {unknown}")
            if task.id in task.depends_on:
                raise ValueError(f"task cannot depend on itself: {task.id}")
        return self


class InformationTraceAudit(BaseModel):
    """Coverage of required information by current runtime data nodes."""

    model_config = ConfigDict(frozen=True)

    required_source_count: int
    traced_source_count: int
    trace_rate: float
    missing_requirement_keys: list[str]
    tasks_without_runtime_widgets: list[str]
    unknown_runtime_data_node_ids: list[str]
    unknown_runtime_widget_ids: list[str]


def load_clinical_task_graph(path: Path) -> ClinicalTaskGraph:
    """Load and validate a clinical task graph JSON file."""

    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    return ClinicalTaskGraph.model_validate(payload)


def audit_information_trace(
    graph: ClinicalTaskGraph,
    *,
    known_data_node_ids: set[str] | None = None,
    known_widget_ids: set[str] | None = None,
) -> InformationTraceAudit:
    """Measure whether required information maps to existing runtime nodes."""

    required_items = [
        (task.id, requirement)
        for task in graph.tasks
        for requirement in task.information_requirements
        if requirement.required and requirement.kind == "source"
    ]
    referenced_data_node_ids = {
        data_node_id
        for _, requirement in required_items
        for data_node_id in requirement.runtime_data_node_ids
    }
    unknown_data_node_ids = (
        sorted(referenced_data_node_ids - known_data_node_ids)
        if known_data_node_ids is not None
        else []
    )
    missing_keys = [
        f"{task_id}.{requirement.id}"
        for task_id, requirement in required_items
        if not requirement.runtime_data_node_ids
        or (
            known_data_node_ids is not None
            and not set(requirement.runtime_data_node_ids) <= known_data_node_ids
        )
    ]
    required_count = len(required_items)
    traced_count = required_count - len(missing_keys)
    trace_rate = traced_count / required_count if required_count else 1.0
    referenced_widget_ids = {
        widget_id for task in graph.tasks for widget_id in task.runtime_widget_ids
    }
    unknown_widget_ids = (
        sorted(referenced_widget_ids - known_widget_ids)
        if known_widget_ids is not None
        else []
    )
    tasks_without_widgets = []
    for task in graph.tasks:
        has_widgets = bool(task.runtime_widget_ids)
        if known_widget_ids is not None:
            has_widgets = has_widgets and set(task.runtime_widget_ids) <= known_widget_ids
        if not has_widgets:
            tasks_without_widgets.append(task.id)
    return InformationTraceAudit(
        required_source_count=required_count,
        traced_source_count=traced_count,
        trace_rate=trace_rate,
        missing_requirement_keys=missing_keys,
        tasks_without_runtime_widgets=tasks_without_widgets,
        unknown_runtime_data_node_ids=unknown_data_node_ids,
        unknown_runtime_widget_ids=unknown_widget_ids,
    )

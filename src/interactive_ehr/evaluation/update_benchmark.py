"""Deterministic benchmark for graph-mediated and direct UI updates."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IdentifiedModel(Protocol):
    """Structural type for benchmark models carrying a stable ID."""

    id: str


class BenchmarkSplit(str, Enum):
    """Dataset split used for development or held-out evaluation."""

    DEVELOPMENT = "development"
    EVALUATION = "evaluation"


class ChangeKind(str, Enum):
    """Representation-independent update requested by one benchmark case."""

    ADD_INFORMATION = "add_information"
    NARROW_TIME_WINDOW = "narrow_time_window"
    CHANGE_VISUALIZATION = "change_visualization"
    REGROUP_DISPLAY = "regroup_display"
    RELABEL_WIDGET = "relabel_widget"
    CHANGE_DATA_SOURCE = "change_data_source"


class FaultKind(str, Enum):
    """Pre-registered fault injected into an otherwise valid update."""

    OUT_OF_SCOPE_MUTATION = "out_of_scope_mutation"
    SAFETY_VIOLATION = "safety_violation"
    TRACEABILITY_BREAK = "traceability_break"
    EXECUTION_FAILURE = "execution_failure"


class UpdateMethod(str, Enum):
    """Update-control condition evaluated by the benchmark."""

    DIRECT = "direct"
    GRAPH_FULL = "graph_full"
    GRAPH_NO_SCOPE = "graph_no_scope"
    GRAPH_NO_SAFETY = "graph_no_safety"
    GRAPH_NO_TRACEABILITY = "graph_no_traceability"


class ReviewStatus(str, Enum):
    """Evidence review state attached to an update request or constraint."""

    DRAFT = "draft"
    EXPERT_REVIEWED = "expert-reviewed"
    SYNTHETIC = "synthetic"


class PatchAction(str, Enum):
    """Supported deterministic patch operation."""

    SET = "set"
    APPEND = "append"
    REMOVE = "remove"


class TaskArtifact(BaseModel):
    """Rendered task container in a direct UI artifact."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    widget_ids: list[str] = Field(default_factory=list)


class WidgetArtifact(BaseModel):
    """Rendered widget and its query binding in a direct UI artifact."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    kind: Literal["table", "cards", "line_chart", "text"]
    query_id: str
    displayed_fields: list[str] = Field(default_factory=list)


class QueryArtifact(BaseModel):
    """Structured query compiled to SQL during technical validation."""

    model_config = ConfigDict(frozen=True)

    id: str
    source_table: str
    selected_fields: list[str] = Field(default_factory=list)
    time_window_days: int | None = Field(None, ge=1)


class ArtifactState(BaseModel):
    """Directly editable UI, query, and task artifacts."""

    model_config = ConfigDict(frozen=True)

    tasks: list[TaskArtifact]
    widgets: list[WidgetArtifact]
    queries: list[QueryArtifact]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Reject duplicate IDs and broken task or query references."""

        _ensure_unique_ids(self.tasks, "task")
        _ensure_unique_ids(self.widgets, "widget")
        _ensure_unique_ids(self.queries, "query")
        widget_ids = {widget.id for widget in self.widgets}
        query_ids = {query.id for query in self.queries}
        task_widget_ids = [widget_id for task in self.tasks for widget_id in task.widget_ids]
        if len(task_widget_ids) != len(set(task_widget_ids)):
            raise ValueError("a widget may belong to only one task")
        unknown_widgets = set(task_widget_ids) - widget_ids
        if unknown_widgets:
            raise ValueError(f"unknown task widget IDs: {sorted(unknown_widgets)}")
        unassigned_widgets = widget_ids - set(task_widget_ids)
        if unassigned_widgets:
            raise ValueError(f"unassigned widget IDs: {sorted(unassigned_widgets)}")
        unknown_queries = {widget.query_id for widget in self.widgets} - query_ids
        if unknown_queries:
            raise ValueError(f"unknown widget query IDs: {sorted(unknown_queries)}")
        return self


class GraphTaskNode(BaseModel):
    """Task node in the benchmark graph representation."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    widget_node_ids: list[str] = Field(default_factory=list)


class GraphWidgetNode(BaseModel):
    """Widget node linked to one graph data node."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    kind: Literal["table", "cards", "line_chart", "text"]
    data_node_id: str
    displayed_fields: list[str] = Field(default_factory=list)


class GraphDataNode(BaseModel):
    """Data node retaining query and information provenance."""

    model_config = ConfigDict(frozen=True)

    id: str
    query_id: str
    source_table: str
    selected_fields: list[str] = Field(default_factory=list)
    information_ids: list[str] = Field(default_factory=list)
    time_window_days: int | None = Field(None, ge=1)


class GraphState(BaseModel):
    """Task, widget, and data nodes used to mediate an update."""

    model_config = ConfigDict(frozen=True)

    task_nodes: list[GraphTaskNode]
    widget_nodes: list[GraphWidgetNode]
    data_nodes: list[GraphDataNode]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Reject duplicate node IDs and broken graph references."""

        _ensure_unique_ids(self.task_nodes, "task node")
        _ensure_unique_ids(self.widget_nodes, "widget node")
        _ensure_unique_ids(self.data_nodes, "data node")
        widget_ids = {widget.id for widget in self.widget_nodes}
        data_ids = {data_node.id for data_node in self.data_nodes}
        owned_widget_ids = [
            widget_id
            for task_node in self.task_nodes
            for widget_id in task_node.widget_node_ids
        ]
        if len(owned_widget_ids) != len(set(owned_widget_ids)):
            raise ValueError("a widget node may belong to only one task node")
        unknown_widgets = set(owned_widget_ids) - widget_ids
        if unknown_widgets:
            raise ValueError(f"unknown task widget node IDs: {sorted(unknown_widgets)}")
        unassigned_widgets = widget_ids - set(owned_widget_ids)
        if unassigned_widgets:
            raise ValueError(f"unassigned widget node IDs: {sorted(unassigned_widgets)}")
        unknown_data = {widget.data_node_id for widget in self.widget_nodes} - data_ids
        if unknown_data:
            raise ValueError(f"unknown widget data node IDs: {sorted(unknown_data)}")
        return self


class SafetyPolicy(BaseModel):
    """Pre-registered structural safety requirements shared by both methods."""

    model_config = ConfigDict(frozen=True)

    id: str
    forbidden_display_fields: list[str] = Field(min_length=1)
    approved_source_tables: list[str] = Field(min_length=1)
    source_reference: str
    review_status: ReviewStatus
    interpretation: str


class UpdateIntent(BaseModel):
    """Representation-independent change requested by a benchmark case."""

    model_config = ConfigDict(frozen=True)

    change_kind: ChangeKind
    target_task_id: str
    target_widget_id: str
    target_query_id: str
    destination_task_id: str | None = None
    requested_field: str | None = None
    requested_title: str | None = None
    requested_widget_kind: Literal["table", "cards", "line_chart", "text"] | None = None
    requested_time_window_days: int | None = Field(None, ge=1)
    requested_source_table: str | None = None

    @model_validator(mode="after")
    def validate_change_payload(self) -> Self:
        """Require the value needed by the selected change kind."""

        required_value_by_kind = {
            ChangeKind.ADD_INFORMATION: self.requested_field,
            ChangeKind.NARROW_TIME_WINDOW: self.requested_time_window_days,
            ChangeKind.CHANGE_VISUALIZATION: self.requested_widget_kind,
            ChangeKind.REGROUP_DISPLAY: self.destination_task_id,
            ChangeKind.RELABEL_WIDGET: self.requested_title,
            ChangeKind.CHANGE_DATA_SOURCE: self.requested_source_table,
        }
        if required_value_by_kind[self.change_kind] is None:
            raise ValueError(f"missing requested value for {self.change_kind.value}")
        return self


class UpdateCase(BaseModel):
    """One frozen update request and its provenance metadata."""

    model_config = ConfigDict(frozen=True)

    id: str
    split: BenchmarkSplit
    source_reference: str
    source_status: ReviewStatus
    source_note: str
    intent: UpdateIntent


class SequenceStep(BaseModel):
    """One update applied to the state produced by the preceding step."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    faults: list[FaultKind] = Field(default_factory=list, max_length=2)


class UpdateSequence(BaseModel):
    """Three-step sequence for testing state accumulation and rejection rollback."""

    model_config = ConfigDict(frozen=True)

    id: str
    split: BenchmarkSplit
    steps: list[SequenceStep] = Field(min_length=3, max_length=3)


class RequirementDefinition(BaseModel):
    """One comparison requirement and how each representation expresses it."""

    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    runtime_comparable: bool
    direct_expression: str
    graph_expression: str
    direct_implementation: list[str]
    graph_implementation: list[str]
    referenced_artifacts: list[str]
    maintenance_touchpoints: list[str]
    tests: list[str]


class BenchmarkDefinition(BaseModel):
    """Versioned input for the deterministic UI update benchmark."""

    model_config = ConfigDict(frozen=True)

    id: str
    version: str
    random_seed: int
    bootstrap_iterations: int = Field(ge=100)
    interpretation_limit: str
    available_fields: list[str]
    source_tables: list[str]
    safety_policy: SafetyPolicy
    requirements: list[RequirementDefinition]
    baseline: ArtifactState
    cases: list[UpdateCase]
    sequences: list[UpdateSequence]

    @model_validator(mode="after")
    def validate_benchmark_shape(self) -> Self:
        """Enforce the pre-registered split, case, and sequence counts."""

        _ensure_unique_ids(self.requirements, "requirement")
        _ensure_unique_ids(self.cases, "update case")
        _ensure_unique_ids(self.sequences, "update sequence")
        development_cases = [
            case for case in self.cases if case.split is BenchmarkSplit.DEVELOPMENT
        ]
        evaluation_cases = [
            case for case in self.cases if case.split is BenchmarkSplit.EVALUATION
        ]
        if len(development_cases) != 8:
            raise ValueError("development split must contain eight one-shot cases")
        if len(evaluation_cases) != 24:
            raise ValueError("evaluation split must contain 24 one-shot cases")
        for change_kind in ChangeKind:
            matching = [
                case for case in evaluation_cases if case.intent.change_kind is change_kind
            ]
            if len(matching) != 4:
                raise ValueError(
                    f"evaluation split must contain four {change_kind.value} cases"
                )
        development_sequences = [
            sequence
            for sequence in self.sequences
            if sequence.split is BenchmarkSplit.DEVELOPMENT
        ]
        evaluation_sequences = [
            sequence
            for sequence in self.sequences
            if sequence.split is BenchmarkSplit.EVALUATION
        ]
        if len(development_sequences) != 2:
            raise ValueError("development split must contain two sequences")
        if len(evaluation_sequences) != 6:
            raise ValueError("evaluation split must contain six sequences")
        self._validate_case_references()
        self._validate_baseline_targets()
        return self

    def _validate_case_references(self) -> None:
        """Ensure every sequence step refers to a case in the same split."""

        cases_by_id = {case.id: case for case in self.cases}
        for sequence in self.sequences:
            for step in sequence.steps:
                if step.case_id not in cases_by_id:
                    raise ValueError(
                        f"unknown sequence case {step.case_id}: {sequence.id}"
                    )
                if cases_by_id[step.case_id].split is not sequence.split:
                    raise ValueError(
                        f"sequence split mismatch for {step.case_id}: {sequence.id}"
                    )

    def _validate_baseline_targets(self) -> None:
        """Ensure update targets and requested sources exist in the benchmark schema."""

        if len(self.available_fields) != len(set(self.available_fields)):
            raise ValueError("available fields must be unique")
        if len(self.source_tables) != len(set(self.source_tables)):
            raise ValueError("source tables must be unique")
        available_fields = set(self.available_fields)
        source_tables = set(self.source_tables)
        if not set(self.safety_policy.forbidden_display_fields).issubset(
            available_fields
        ):
            raise ValueError("forbidden display fields must exist in the schema")
        if not set(self.safety_policy.approved_source_tables).issubset(source_tables):
            raise ValueError("approved sources must exist in the schema")
        tasks = {task.id: task for task in self.baseline.tasks}
        widgets = {widget.id: widget for widget in self.baseline.widgets}
        queries = {query.id: query for query in self.baseline.queries}
        for widget in self.baseline.widgets:
            query = queries[widget.query_id]
            if not set(widget.displayed_fields).issubset(query.selected_fields):
                raise ValueError(f"baseline traceability gap: {widget.id}")
        for query in self.baseline.queries:
            if query.source_table not in source_tables:
                raise ValueError(f"unknown baseline source: {query.id}")
            if not set(query.selected_fields).issubset(available_fields):
                raise ValueError(f"unknown baseline field: {query.id}")
        for case in self.cases:
            intent = case.intent
            if intent.target_task_id not in tasks:
                raise ValueError(f"unknown target task: {case.id}")
            if intent.target_widget_id not in widgets:
                raise ValueError(f"unknown target widget: {case.id}")
            if intent.target_query_id not in queries:
                raise ValueError(f"unknown target query: {case.id}")
            if widgets[intent.target_widget_id].query_id != intent.target_query_id:
                raise ValueError(f"widget and query target mismatch: {case.id}")
            if intent.target_widget_id not in tasks[intent.target_task_id].widget_ids:
                raise ValueError(f"widget and task target mismatch: {case.id}")
            if (
                intent.destination_task_id is not None
                and intent.destination_task_id not in tasks
            ):
                raise ValueError(f"unknown destination task: {case.id}")
            if (
                intent.requested_field is not None
                and intent.requested_field not in self.available_fields
            ):
                raise ValueError(f"unknown requested field: {case.id}")
            if (
                intent.requested_source_table is not None
                and intent.requested_source_table not in self.source_tables
            ):
                raise ValueError(f"unknown requested source: {case.id}")
            self._validate_intent_changes_state(case, tasks, widgets, queries)

    def _validate_intent_changes_state(
        self,
        case: UpdateCase,
        tasks: dict[str, TaskArtifact],
        widgets: dict[str, WidgetArtifact],
        queries: dict[str, QueryArtifact],
    ) -> None:
        """Reject a requested update that is already true in the baseline."""

        intent = case.intent
        widget = widgets[intent.target_widget_id]
        query = queries[intent.target_query_id]
        if intent.change_kind is ChangeKind.ADD_INFORMATION:
            if (
                intent.requested_field in widget.displayed_fields
                or intent.requested_field in query.selected_fields
            ):
                raise ValueError(f"requested field already exists: {case.id}")
        elif intent.change_kind is ChangeKind.NARROW_TIME_WINDOW:
            if (
                query.time_window_days is None
                or intent.requested_time_window_days is None
                or intent.requested_time_window_days >= query.time_window_days
            ):
                raise ValueError(f"time window is not narrower: {case.id}")
        elif intent.change_kind is ChangeKind.CHANGE_VISUALIZATION:
            if intent.requested_widget_kind == widget.kind:
                raise ValueError(f"visualization does not change: {case.id}")
        elif intent.change_kind is ChangeKind.REGROUP_DISPLAY:
            if (
                intent.destination_task_id == intent.target_task_id
                or intent.destination_task_id is None
                or intent.target_widget_id in tasks[intent.destination_task_id].widget_ids
            ):
                raise ValueError(f"display grouping does not change: {case.id}")
        elif intent.change_kind is ChangeKind.RELABEL_WIDGET:
            if intent.requested_title == widget.title:
                raise ValueError(f"widget label does not change: {case.id}")
        elif intent.requested_source_table == query.source_table:
            raise ValueError(f"data source does not change: {case.id}")
        if (
            intent.requested_source_table is not None
            and intent.requested_source_table
            not in self.safety_policy.approved_source_tables
        ):
            raise ValueError(f"requested source is not approved: {case.id}")


class PatchOperation(BaseModel):
    """Single operation in a generated direct or graph patch."""

    model_config = ConfigDict(frozen=True)

    entity: Literal[
        "task",
        "widget",
        "query",
        "task_node",
        "widget_node",
        "data_node",
    ]
    entity_id: str
    field: str
    action: PatchAction
    value: str | int


class UpdatePatch(BaseModel):
    """Deterministically generated patch candidate."""

    model_config = ConfigDict(frozen=True)

    version: str
    candidate_id: str
    representation: Literal["direct", "graph"]
    operations: list[PatchOperation]


class CandidateSpec(BaseModel):
    """Common candidate label from which both patches are generated."""

    model_config = ConfigDict(frozen=True)

    version: str
    id: str
    case_id: str
    faults: list[FaultKind] = Field(default_factory=list, max_length=2)
    expected_valid: bool
    checksum: str


class PairedCandidate(BaseModel):
    """One common specification and its two corresponding patch checksums."""

    model_config = ConfigDict(frozen=True)

    version: str
    specification: CandidateSpec
    direct_patch: UpdatePatch
    graph_patch: UpdatePatch
    direct_patch_checksum: str
    graph_patch_checksum: str


class ValidationResult(BaseModel):
    """Result of one independent runtime validation check."""

    model_config = ConfigDict(frozen=True)

    check_id: str
    passed: bool
    detail: str


class CandidateRunRecord(BaseModel):
    """Observed decision for one candidate under one comparison method."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    split: BenchmarkSplit
    candidate_id: str
    method: UpdateMethod
    faults: list[FaultKind]
    expected_valid: bool
    oracle_valid: bool
    accepted: bool
    safe_rejection: bool
    unsafe_acceptance: bool
    runtime_failure: bool
    representation_equivalent: bool
    validation_results: list[ValidationResult]
    final_state_checksum: str


class SequenceRunRecord(BaseModel):
    """Observed decision and rollback state for one sequential update step."""

    model_config = ConfigDict(frozen=True)

    sequence_id: str
    split: BenchmarkSplit
    step_index: int
    case_id: str
    method: UpdateMethod
    faults: list[FaultKind]
    oracle_valid: bool
    accepted: bool
    state_preserved_after_rejection: bool
    committed_state_checksum: str


class BenchmarkRun(BaseModel):
    """All deterministic one-shot and sequential observations."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    benchmark_version: str
    benchmark_checksum: str
    paired_candidates: list[PairedCandidate]
    candidate_records: list[CandidateRunRecord]
    sequence_records: list[SequenceRunRecord]


def load_update_benchmark(path: Path) -> BenchmarkDefinition:
    """Load and validate a UI update benchmark JSON file."""

    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    return BenchmarkDefinition.model_validate(payload)


def canonical_checksum(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    """Return a stable SHA-256 checksum for JSON-compatible content."""

    payload: Any = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def artifact_to_graph(artifact: ArtifactState) -> GraphState:
    """Create the initial graph state corresponding to a direct artifact."""

    data_nodes = [
        GraphDataNode(
            id=f"data_{query.id}",
            query_id=query.id,
            source_table=query.source_table,
            selected_fields=query.selected_fields,
            information_ids=query.selected_fields,
            time_window_days=query.time_window_days,
        )
        for query in artifact.queries
    ]
    data_id_by_query = {node.query_id: node.id for node in data_nodes}
    return GraphState(
        task_nodes=[
            GraphTaskNode(
                id=task.id,
                title=task.title,
                widget_node_ids=task.widget_ids,
            )
            for task in artifact.tasks
        ],
        widget_nodes=[
            GraphWidgetNode(
                id=widget.id,
                title=widget.title,
                kind=widget.kind,
                data_node_id=data_id_by_query[widget.query_id],
                displayed_fields=widget.displayed_fields,
            )
            for widget in artifact.widgets
        ],
        data_nodes=data_nodes,
    )


def compile_graph_artifact(graph: GraphState) -> ArtifactState:
    """Compile a graph state into the artifacts used for semantic comparison."""

    data_by_id = {data_node.id: data_node for data_node in graph.data_nodes}
    return ArtifactState(
        tasks=[
            TaskArtifact(
                id=task_node.id,
                title=task_node.title,
                widget_ids=task_node.widget_node_ids,
            )
            for task_node in graph.task_nodes
        ],
        widgets=[
            WidgetArtifact(
                id=widget_node.id,
                title=widget_node.title,
                kind=widget_node.kind,
                query_id=data_by_id[widget_node.data_node_id].query_id,
                displayed_fields=widget_node.displayed_fields,
            )
            for widget_node in graph.widget_nodes
        ],
        queries=[
            QueryArtifact(
                id=data_node.query_id,
                source_table=data_node.source_table,
                selected_fields=data_node.selected_fields,
                time_window_days=data_node.time_window_days,
            )
            for data_node in graph.data_nodes
        ],
    )


def build_candidate_specs(benchmark: BenchmarkDefinition) -> list[CandidateSpec]:
    """Expand each one-shot case into one valid and four invalid candidates."""

    fault_kinds = list(FaultKind)
    specifications: list[CandidateSpec] = []
    for index, case in enumerate(benchmark.cases):
        common_payload = {"case_id": case.id, "faults": []}
        specifications.append(
            _build_candidate_spec(
                version=benchmark.version,
                candidate_id=f"{case.id}:valid",
                common_payload=common_payload,
            )
        )
        omitted_fault = fault_kinds[index % len(fault_kinds)]
        for fault in fault_kinds:
            if fault is omitted_fault:
                continue
            single_payload = {"case_id": case.id, "faults": [fault.value]}
            specifications.append(
                _build_candidate_spec(
                    version=benchmark.version,
                    candidate_id=f"{case.id}:single:{fault.value}",
                    common_payload=single_payload,
                )
            )
        compound_partner = (
            FaultKind.TRACEABILITY_BREAK
            if omitted_fault is FaultKind.SAFETY_VIOLATION
            else FaultKind.SAFETY_VIOLATION
        )
        compound_payload = {
            "case_id": case.id,
            "faults": [omitted_fault.value, compound_partner.value],
        }
        specifications.append(
            _build_candidate_spec(
                version=benchmark.version,
                candidate_id=f"{case.id}:compound",
                common_payload=compound_payload,
            )
        )
    return specifications


def _build_candidate_spec(
    *,
    version: str,
    candidate_id: str,
    common_payload: dict[str, Any],
) -> CandidateSpec:
    """Create one candidate with a checksum independent of representation."""

    faults = [FaultKind(value) for value in common_payload["faults"]]
    checksum_payload = {
        "version": version,
        "candidate_id": candidate_id,
        "case_id": common_payload["case_id"],
        "faults": [fault.value for fault in faults],
    }
    return CandidateSpec(
        version=version,
        id=candidate_id,
        case_id=str(common_payload["case_id"]),
        faults=faults,
        expected_valid=not faults,
        checksum=canonical_checksum(checksum_payload),
    )


def build_paired_candidate(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    specification: CandidateSpec,
) -> PairedCandidate:
    """Generate semantically corresponding direct and graph patches."""

    if specification.version != benchmark.version:
        raise ValueError("candidate and benchmark versions must match")
    direct_patch = _build_direct_patch(benchmark, case, specification)
    graph_patch = _build_graph_patch(benchmark, case, specification)
    return PairedCandidate(
        version=benchmark.version,
        specification=specification,
        direct_patch=direct_patch,
        graph_patch=graph_patch,
        direct_patch_checksum=canonical_checksum(direct_patch),
        graph_patch_checksum=canonical_checksum(graph_patch),
    )


def apply_artifact_patch(state: ArtifactState, patch: UpdatePatch) -> ArtifactState:
    """Apply a direct patch without running any acceptance checks."""

    if patch.representation != "direct":
        raise ValueError("artifact state requires a direct patch")
    payload = state.model_dump(mode="json")
    for operation in patch.operations:
        _apply_operation(payload, operation, graph=False)
    return ArtifactState.model_validate(payload)


def apply_graph_patch(state: GraphState, patch: UpdatePatch) -> GraphState:
    """Apply a graph patch without running any acceptance checks."""

    if patch.representation != "graph":
        raise ValueError("graph state requires a graph patch")
    payload = state.model_dump(mode="json")
    for operation in patch.operations:
        _apply_operation(payload, operation, graph=True)
    return GraphState.model_validate(payload)


def evaluate_candidate(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    paired_candidate: PairedCandidate,
    method: UpdateMethod,
    *,
    artifact_state: ArtifactState | None = None,
    graph_state: GraphState | None = None,
) -> CandidateRunRecord:
    """Apply one candidate and evaluate it under one update-control method."""

    initial_artifact = artifact_state or benchmark.baseline
    initial_graph = graph_state or artifact_to_graph(initial_artifact)
    direct_candidate = apply_artifact_patch(
        initial_artifact,
        paired_candidate.direct_patch,
    )
    graph_candidate = apply_graph_patch(initial_graph, paired_candidate.graph_patch)
    compiled_graph_candidate = compile_graph_artifact(graph_candidate)
    equivalent = direct_candidate == compiled_graph_candidate
    oracle_valid = semantic_oracle(
        benchmark,
        case,
        initial_artifact,
        direct_candidate,
    )
    if method is UpdateMethod.DIRECT:
        validations = _validate_direct_candidate(
            benchmark,
            case,
            initial_artifact,
            direct_candidate,
        )
        final_artifact = direct_candidate
    else:
        validations = _validate_graph_candidate(
            benchmark,
            case,
            initial_graph,
            graph_candidate,
            method,
        )
        final_artifact = compiled_graph_candidate
    accepted = equivalent and all(result.passed for result in validations)
    runtime_failure = any(
        result.check_id == "query_execution" and not result.passed
        for result in validations
    )
    return CandidateRunRecord(
        case_id=case.id,
        split=case.split,
        candidate_id=paired_candidate.specification.id,
        method=method,
        faults=paired_candidate.specification.faults,
        expected_valid=paired_candidate.specification.expected_valid,
        oracle_valid=oracle_valid,
        accepted=accepted,
        safe_rejection=not accepted and not oracle_valid,
        unsafe_acceptance=accepted and not oracle_valid,
        runtime_failure=runtime_failure,
        representation_equivalent=equivalent,
        validation_results=validations,
        final_state_checksum=canonical_checksum(final_artifact),
    )


def semantic_oracle(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    before: ArtifactState,
    candidate: ArtifactState,
) -> bool:
    """Judge semantics independently from the runtime validator functions."""

    intent = case.intent
    task_by_id = {task.id: task for task in candidate.tasks}
    widget_by_id = {widget.id: widget for widget in candidate.widgets}
    query_by_id = {query.id: query for query in candidate.queries}
    widget = widget_by_id[intent.target_widget_id]
    query = query_by_id[intent.target_query_id]

    if not _oracle_intent_satisfied(intent, task_by_id, widget, query):
        return False
    if _changed_entity_keys(before, candidate) - _allowed_entity_keys(case):
        return False
    forbidden_fields = set(benchmark.safety_policy.forbidden_display_fields)
    if any(
        forbidden_fields.intersection(item.displayed_fields)
        for item in candidate.widgets
    ):
        return False
    if any(
        query_item.source_table not in benchmark.safety_policy.approved_source_tables
        for query_item in candidate.queries
    ):
        return False
    candidate_queries = {item.id: item for item in candidate.queries}
    if any(
        not set(item.displayed_fields).issubset(
            candidate_queries[item.query_id].selected_fields
        )
        for item in candidate.widgets
    ):
        return False
    return _oracle_queries_match_schema(benchmark, candidate)


def run_update_benchmark(benchmark: BenchmarkDefinition) -> BenchmarkRun:
    """Run all one-shot candidates and sequential cases exactly once."""

    cases_by_id = {case.id: case for case in benchmark.cases}
    specifications = build_candidate_specs(benchmark)
    paired_candidates = [
        build_paired_candidate(
            benchmark,
            cases_by_id[specification.case_id],
            specification,
        )
        for specification in specifications
    ]
    candidate_records = [
        evaluate_candidate(
            benchmark,
            cases_by_id[paired.specification.case_id],
            paired,
            method,
        )
        for paired in paired_candidates
        for method in UpdateMethod
    ]
    sequence_records = _run_sequences(benchmark, cases_by_id)
    return BenchmarkRun(
        benchmark_id=benchmark.id,
        benchmark_version=benchmark.version,
        benchmark_checksum=canonical_checksum(benchmark),
        paired_candidates=paired_candidates,
        candidate_records=candidate_records,
        sequence_records=sequence_records,
    )


def _run_sequences(
    benchmark: BenchmarkDefinition,
    cases_by_id: dict[str, UpdateCase],
) -> list[SequenceRunRecord]:
    """Run sequential updates while retaining state only after acceptance."""

    records: list[SequenceRunRecord] = []
    for sequence in benchmark.sequences:
        for method in UpdateMethod:
            artifact_state = benchmark.baseline
            graph_state = artifact_to_graph(artifact_state)
            for step_index, step in enumerate(sequence.steps, start=1):
                case = cases_by_id[step.case_id]
                specification = _build_candidate_spec(
                    version=benchmark.version,
                    candidate_id=f"{sequence.id}:step:{step_index}",
                    common_payload={
                        "case_id": case.id,
                        "faults": [fault.value for fault in step.faults],
                    },
                )
                paired = build_paired_candidate(benchmark, case, specification)
                before_checksum = _committed_checksum(method, artifact_state, graph_state)
                record = evaluate_candidate(
                    benchmark,
                    case,
                    paired,
                    method,
                    artifact_state=artifact_state,
                    graph_state=graph_state,
                )
                if record.accepted:
                    if method is UpdateMethod.DIRECT:
                        artifact_state = apply_artifact_patch(
                            artifact_state,
                            paired.direct_patch,
                        )
                        graph_state = artifact_to_graph(artifact_state)
                    else:
                        graph_state = apply_graph_patch(graph_state, paired.graph_patch)
                        artifact_state = compile_graph_artifact(graph_state)
                after_checksum = _committed_checksum(method, artifact_state, graph_state)
                records.append(
                    SequenceRunRecord(
                        sequence_id=sequence.id,
                        split=sequence.split,
                        step_index=step_index,
                        case_id=case.id,
                        method=method,
                        faults=step.faults,
                        oracle_valid=record.oracle_valid,
                        accepted=record.accepted,
                        state_preserved_after_rejection=(
                            record.accepted or before_checksum == after_checksum
                        ),
                        committed_state_checksum=after_checksum,
                    )
                )
    return records


def _committed_checksum(
    method: UpdateMethod,
    artifact_state: ArtifactState,
    graph_state: GraphState,
) -> str:
    """Return the checksum of the state committed by one method."""

    if method is UpdateMethod.DIRECT:
        return canonical_checksum(artifact_state)
    return canonical_checksum(graph_state)


def _build_direct_patch(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    specification: CandidateSpec,
) -> UpdatePatch:
    """Generate a direct artifact patch from a common candidate spec."""

    operations = _valid_operations(case, graph=False)
    operations.extend(
        _fault_operations(
            benchmark,
            case,
            specification.faults,
            graph=False,
        )
    )
    return UpdatePatch(
        version=benchmark.version,
        candidate_id=specification.id,
        representation="direct",
        operations=operations,
    )


def _build_graph_patch(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    specification: CandidateSpec,
) -> UpdatePatch:
    """Generate a graph patch from the same common candidate spec."""

    operations = _valid_operations(case, graph=True)
    operations.extend(
        _fault_operations(
            benchmark,
            case,
            specification.faults,
            graph=True,
        )
    )
    return UpdatePatch(
        version=benchmark.version,
        candidate_id=specification.id,
        representation="graph",
        operations=operations,
    )


def _valid_operations(case: UpdateCase, *, graph: bool) -> list[PatchOperation]:
    """Translate a valid change intent into representation-specific operations."""

    intent = case.intent
    widget_entity = "widget_node" if graph else "widget"
    data_entity = "data_node" if graph else "query"
    task_entity = "task_node" if graph else "task"
    data_id = f"data_{intent.target_query_id}" if graph else intent.target_query_id

    if intent.change_kind is ChangeKind.ADD_INFORMATION:
        assert intent.requested_field is not None
        operations = [
            PatchOperation(
                entity=widget_entity,
                entity_id=intent.target_widget_id,
                field="displayed_fields",
                action=PatchAction.APPEND,
                value=intent.requested_field,
            ),
            PatchOperation(
                entity=data_entity,
                entity_id=data_id,
                field="selected_fields",
                action=PatchAction.APPEND,
                value=intent.requested_field,
            ),
        ]
        if graph:
            operations.append(
                PatchOperation(
                    entity="data_node",
                    entity_id=data_id,
                    field="information_ids",
                    action=PatchAction.APPEND,
                    value=intent.requested_field,
                )
            )
        return operations
    if intent.change_kind is ChangeKind.NARROW_TIME_WINDOW:
        assert intent.requested_time_window_days is not None
        return [
            PatchOperation(
                entity=data_entity,
                entity_id=data_id,
                field="time_window_days",
                action=PatchAction.SET,
                value=intent.requested_time_window_days,
            )
        ]
    if intent.change_kind is ChangeKind.CHANGE_VISUALIZATION:
        assert intent.requested_widget_kind is not None
        return [
            PatchOperation(
                entity=widget_entity,
                entity_id=intent.target_widget_id,
                field="kind",
                action=PatchAction.SET,
                value=intent.requested_widget_kind,
            )
        ]
    if intent.change_kind is ChangeKind.REGROUP_DISPLAY:
        assert intent.destination_task_id is not None
        widget_list_field = "widget_node_ids" if graph else "widget_ids"
        return [
            PatchOperation(
                entity=task_entity,
                entity_id=intent.target_task_id,
                field=widget_list_field,
                action=PatchAction.REMOVE,
                value=intent.target_widget_id,
            ),
            PatchOperation(
                entity=task_entity,
                entity_id=intent.destination_task_id,
                field=widget_list_field,
                action=PatchAction.APPEND,
                value=intent.target_widget_id,
            ),
        ]
    if intent.change_kind is ChangeKind.RELABEL_WIDGET:
        assert intent.requested_title is not None
        return [
            PatchOperation(
                entity=widget_entity,
                entity_id=intent.target_widget_id,
                field="title",
                action=PatchAction.SET,
                value=intent.requested_title,
            )
        ]
    assert intent.requested_source_table is not None
    return [
        PatchOperation(
            entity=data_entity,
            entity_id=data_id,
            field="source_table",
            action=PatchAction.SET,
            value=intent.requested_source_table,
        )
    ]


def _fault_operations(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    faults: Iterable[FaultKind],
    *,
    graph: bool,
) -> list[PatchOperation]:
    """Translate pre-registered faults without using runtime validation code."""

    intent = case.intent
    widget_entity = "widget_node" if graph else "widget"
    data_entity = "data_node" if graph else "query"
    data_id = f"data_{intent.target_query_id}" if graph else intent.target_query_id
    operations: list[PatchOperation] = []
    for fault in faults:
        if fault is FaultKind.OUT_OF_SCOPE_MUTATION:
            protected_widget_id = next(
                widget.id
                for widget in benchmark.baseline.widgets
                if widget.id != intent.target_widget_id
            )
            operations.append(
                PatchOperation(
                    entity=widget_entity,
                    entity_id=protected_widget_id,
                    field="title",
                    action=PatchAction.SET,
                    value="範囲外の変更",
                )
            )
        elif fault is FaultKind.SAFETY_VIOLATION:
            forbidden_field = benchmark.safety_policy.forbidden_display_fields[0]
            operations.extend(
                [
                    PatchOperation(
                        entity=widget_entity,
                        entity_id=intent.target_widget_id,
                        field="displayed_fields",
                        action=PatchAction.APPEND,
                        value=forbidden_field,
                    ),
                    PatchOperation(
                        entity=data_entity,
                        entity_id=data_id,
                        field="selected_fields",
                        action=PatchAction.APPEND,
                        value=forbidden_field,
                    ),
                ]
            )
            if graph:
                operations.append(
                    PatchOperation(
                        entity="data_node",
                        entity_id=data_id,
                        field="information_ids",
                        action=PatchAction.APPEND,
                        value=forbidden_field,
                    )
                )
        elif fault is FaultKind.TRACEABILITY_BREAK:
            operations.append(
                PatchOperation(
                    entity=widget_entity,
                    entity_id=intent.target_widget_id,
                    field="displayed_fields",
                    action=PatchAction.APPEND,
                    value="trace_gap",
                )
            )
        elif fault is FaultKind.EXECUTION_FAILURE:
            operations.extend(
                [
                    PatchOperation(
                        entity=widget_entity,
                        entity_id=intent.target_widget_id,
                        field="displayed_fields",
                        action=PatchAction.APPEND,
                        value="missing_column",
                    ),
                    PatchOperation(
                        entity=data_entity,
                        entity_id=data_id,
                        field="selected_fields",
                        action=PatchAction.APPEND,
                        value="missing_column",
                    ),
                ]
            )
            if graph:
                operations.append(
                    PatchOperation(
                        entity="data_node",
                        entity_id=data_id,
                        field="information_ids",
                        action=PatchAction.APPEND,
                        value="missing_column",
                    )
                )
    return operations


def _apply_operation(
    payload: dict[str, Any],
    operation: PatchOperation,
    *,
    graph: bool,
) -> None:
    """Apply one typed operation to a mutable model payload."""

    collection_by_entity = (
        {
            "task_node": "task_nodes",
            "widget_node": "widget_nodes",
            "data_node": "data_nodes",
        }
        if graph
        else {"task": "tasks", "widget": "widgets", "query": "queries"}
    )
    if operation.entity not in collection_by_entity:
        raise ValueError(f"invalid operation entity: {operation.entity}")
    collection = payload[collection_by_entity[operation.entity]]
    target = next(
        (item for item in collection if item["id"] == operation.entity_id),
        None,
    )
    if target is None:
        raise ValueError(f"patch target does not exist: {operation.entity_id}")
    if operation.action is PatchAction.SET:
        target[operation.field] = operation.value
        return
    values = target[operation.field]
    if not isinstance(values, list):
        raise ValueError(f"patch field is not a list: {operation.field}")
    if operation.action is PatchAction.APPEND:
        if operation.value not in values:
            values.append(operation.value)
        return
    if operation.value not in values:
        raise ValueError(f"patch value does not exist: {operation.value}")
    values.remove(operation.value)


def _validate_direct_candidate(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    before: ArtifactState,
    candidate: ArtifactState,
) -> list[ValidationResult]:
    """Run the direct artifact validators used in the main comparison."""

    return [
        _validate_direct_scope(case, before, candidate),
        _validate_artifact_safety(benchmark, candidate),
        _validate_artifact_trace(candidate),
        _validate_queries_execute(benchmark, candidate),
    ]


def _validate_graph_candidate(
    benchmark: BenchmarkDefinition,
    case: UpdateCase,
    before: GraphState,
    candidate: GraphState,
    method: UpdateMethod,
) -> list[ValidationResult]:
    """Run full or ablated graph validators plus common execution checks."""

    validations: list[ValidationResult] = []
    if method is not UpdateMethod.GRAPH_NO_SCOPE:
        validations.append(_validate_graph_scope(case, before, candidate))
    if method is not UpdateMethod.GRAPH_NO_SAFETY:
        validations.append(
            _validate_artifact_safety(benchmark, compile_graph_artifact(candidate))
        )
    if method is not UpdateMethod.GRAPH_NO_TRACEABILITY:
        validations.append(_validate_graph_trace(candidate))
    validations.append(
        _validate_queries_execute(benchmark, compile_graph_artifact(candidate))
    )
    return validations


def _validate_direct_scope(
    case: UpdateCase,
    before: ArtifactState,
    candidate: ArtifactState,
) -> ValidationResult:
    """Check that a direct diff touches only the requested semantic entities."""

    unexpected = sorted(
        _changed_entity_keys(before, candidate) - _allowed_entity_keys(case)
    )
    return ValidationResult(
        check_id="scope",
        passed=not unexpected,
        detail="ok" if not unexpected else f"unexpected entities: {unexpected}",
    )


def _validate_graph_scope(
    case: UpdateCase,
    before: GraphState,
    candidate: GraphState,
) -> ValidationResult:
    """Check graph node mutations against the requested node scope."""

    unexpected = sorted(
        _changed_graph_entity_keys(before, candidate) - _allowed_graph_entity_keys(case)
    )
    return ValidationResult(
        check_id="scope",
        passed=not unexpected,
        detail="ok" if not unexpected else f"unexpected nodes: {unexpected}",
    )


def _validate_artifact_safety(
    benchmark: BenchmarkDefinition,
    candidate: ArtifactState,
) -> ValidationResult:
    """Apply the same structural safety policy to either representation."""

    forbidden = set(benchmark.safety_policy.forbidden_display_fields)
    exposed = sorted(
        {
            field
            for widget in candidate.widgets
            for field in widget.displayed_fields
            if field in forbidden
        }
    )
    unapproved_sources = sorted(
        {
            query.source_table
            for query in candidate.queries
            if query.source_table not in benchmark.safety_policy.approved_source_tables
        }
    )
    passed = not exposed and not unapproved_sources
    detail = "ok" if passed else f"forbidden={exposed}, sources={unapproved_sources}"
    return ValidationResult(check_id="safety", passed=passed, detail=detail)


def _validate_artifact_trace(candidate: ArtifactState) -> ValidationResult:
    """Check display-to-query field traceability in direct artifacts."""

    queries = {query.id: query for query in candidate.queries}
    gaps = sorted(
        f"{widget.id}.{field}"
        for widget in candidate.widgets
        for field in set(widget.displayed_fields) - set(queries[widget.query_id].selected_fields)
    )
    return ValidationResult(
        check_id="traceability",
        passed=not gaps,
        detail="ok" if not gaps else f"untraced fields: {gaps}",
    )


def _validate_graph_trace(candidate: GraphState) -> ValidationResult:
    """Check widget-to-data field traceability through graph edges."""

    data_nodes = {data_node.id: data_node for data_node in candidate.data_nodes}
    gaps = sorted(
        f"{widget.id}.{field}"
        for widget in candidate.widget_nodes
        for field in set(widget.displayed_fields)
        - set(data_nodes[widget.data_node_id].selected_fields)
    )
    return ValidationResult(
        check_id="traceability",
        passed=not gaps,
        detail="ok" if not gaps else f"untraced fields: {gaps}",
    )


def _validate_graph_provenance(candidate: GraphState) -> ValidationResult:
    """Check graph-native information provenance outside the main fault model."""

    gaps = sorted(
        f"{data_node.id}.{field}"
        for data_node in candidate.data_nodes
        for field in set(data_node.selected_fields) - set(data_node.information_ids)
    )
    return ValidationResult(
        check_id="graph_provenance",
        passed=not gaps,
        detail="ok" if not gaps else f"missing information IDs: {gaps}",
    )


def _validate_queries_execute(
    benchmark: BenchmarkDefinition,
    candidate: ArtifactState,
) -> ValidationResult:
    """Execute every compiled query against an isolated in-memory schema."""

    passed = _all_queries_execute(benchmark, candidate)
    return ValidationResult(
        check_id="query_execution",
        passed=passed,
        detail="ok" if passed else "one or more compiled queries failed",
    )


def _all_queries_execute(
    benchmark: BenchmarkDefinition,
    candidate: ArtifactState,
) -> bool:
    """Return whether all candidate queries execute on the benchmark schema."""

    available_fields = set(benchmark.available_fields)
    source_tables = set(benchmark.source_tables)
    if any(
        query.source_table not in source_tables
        or not set(query.selected_fields).issubset(available_fields)
        for query in candidate.queries
    ):
        return False
    connection = sqlite3.connect(":memory:")
    try:
        column_sql = ", ".join(
            f"{_quote_identifier(field)} TEXT" for field in benchmark.available_fields
        )
        for source_table in benchmark.source_tables:
            connection.execute(
                f"CREATE TABLE {_quote_identifier(source_table)} ({column_sql})"
            )
        for query in candidate.queries:
            connection.execute(_compile_query(query)).fetchall()
    except sqlite3.Error:
        return False
    finally:
        connection.close()
    return True


def _oracle_queries_match_schema(
    benchmark: BenchmarkDefinition,
    candidate: ArtifactState,
) -> bool:
    """Check query semantics without calling the runtime execution validator."""

    registered_sources = set(benchmark.source_tables)
    registered_fields = set(benchmark.available_fields)
    for query in candidate.queries:
        if query.source_table not in registered_sources:
            return False
        for field in query.selected_fields:
            if field not in registered_fields:
                return False
    return True


def _compile_query(query: QueryArtifact) -> str:
    """Compile a structured benchmark query into read-only SQLite SQL."""

    selected_fields = ", ".join(
        _quote_identifier(field) for field in query.selected_fields
    )
    sql = f"SELECT {selected_fields} FROM {_quote_identifier(query.source_table)}"
    if query.time_window_days is not None:
        sql += (
            f" WHERE {_quote_identifier('recorded_days_ago')}"
            f" <= {query.time_window_days}"
        )
    return sql


def _quote_identifier(value: str) -> str:
    """Quote an SQLite identifier used by a frozen synthetic schema."""

    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _oracle_intent_satisfied(
    intent: UpdateIntent,
    tasks: dict[str, TaskArtifact],
    widget: WidgetArtifact,
    query: QueryArtifact,
) -> bool:
    """Check the requested semantic change without calling runtime validators."""

    if intent.change_kind is ChangeKind.ADD_INFORMATION:
        return (
            intent.requested_field in widget.displayed_fields
            and intent.requested_field in query.selected_fields
        )
    if intent.change_kind is ChangeKind.NARROW_TIME_WINDOW:
        return query.time_window_days == intent.requested_time_window_days
    if intent.change_kind is ChangeKind.CHANGE_VISUALIZATION:
        return widget.kind == intent.requested_widget_kind
    if intent.change_kind is ChangeKind.REGROUP_DISPLAY:
        assert intent.destination_task_id is not None
        return (
            intent.target_widget_id not in tasks[intent.target_task_id].widget_ids
            and intent.target_widget_id in tasks[intent.destination_task_id].widget_ids
        )
    if intent.change_kind is ChangeKind.RELABEL_WIDGET:
        return widget.title == intent.requested_title
    return query.source_table == intent.requested_source_table


def _allowed_entity_keys(case: UpdateCase) -> set[str]:
    """Return entity-level scope shared across the two representations."""

    intent = case.intent
    allowed = {
        f"task:{intent.target_task_id}",
        f"widget:{intent.target_widget_id}",
        f"query:{intent.target_query_id}",
    }
    if intent.destination_task_id is not None:
        allowed.add(f"task:{intent.destination_task_id}")
    return allowed


def _allowed_graph_entity_keys(case: UpdateCase) -> set[str]:
    """Map the common semantic scope to graph node IDs."""

    return {
        key.replace("task:", "task_node:")
        .replace("widget:", "widget_node:")
        .replace("query:", "data_node:data_")
        for key in _allowed_entity_keys(case)
    }


def _changed_entity_keys(
    before: ArtifactState,
    candidate: ArtifactState,
) -> set[str]:
    """Return artifact entities whose serialized values changed."""

    return _changed_keys(before.tasks, candidate.tasks, "task") | _changed_keys(
        before.widgets,
        candidate.widgets,
        "widget",
    ) | _changed_keys(before.queries, candidate.queries, "query")


def _changed_graph_entity_keys(
    before: GraphState,
    candidate: GraphState,
) -> set[str]:
    """Return graph nodes whose serialized values changed."""

    return _changed_keys(
        before.task_nodes,
        candidate.task_nodes,
        "task_node",
    ) | _changed_keys(
        before.widget_nodes,
        candidate.widget_nodes,
        "widget_node",
    ) | _changed_keys(before.data_nodes, candidate.data_nodes, "data_node")


def _changed_keys(
    before: Sequence[IdentifiedModel],
    candidate: Sequence[IdentifiedModel],
    prefix: str,
) -> set[str]:
    """Compare model collections by ID and return changed entity keys."""

    before_by_id = {str(item.id): item for item in before}
    candidate_by_id = {str(item.id): item for item in candidate}
    all_ids = before_by_id.keys() | candidate_by_id.keys()
    return {
        f"{prefix}:{item_id}"
        for item_id in all_ids
        if before_by_id.get(item_id) != candidate_by_id.get(item_id)
    }


def _ensure_unique_ids(items: Sequence[Any], label: str) -> None:
    """Raise a validation error when a model collection repeats an ID."""

    ids = [str(item.id) for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} IDs must be unique")

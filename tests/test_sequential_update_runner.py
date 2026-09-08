"""Test actual updater routing with deterministic transport before paid calls."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from interactive_ehr.evaluation.sequential_update_pilot import initial_graph, prepare
from interactive_ehr.evaluation.generated_update_pilot import save_json


def runner_module() -> ModuleType:
    """Import the CLI without making any API request."""
    spec = importlib.util.spec_from_file_location(
        "sequential_runner",
        Path(__file__).parents[1] / "scripts/run_sequential_update_pilot.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeModels:
    """Supply deterministic data-scope responses to the real routing code."""

    def __init__(self, *, fail: bool = False) -> None:
        """Record requests and optionally simulate an API failure."""
        self.requests: list[dict[str, Any]] = []
        self.fail = fail

    def generate_content(self, **kwargs: Any) -> Any:
        """Return scope then SQL with the unchanged production schema."""
        self.requests.append(kwargs)
        if self.fail:
            raise ConnectionError("secret URL should not be stored")
        if len(self.requests) % 2:
            payload = {"scope": "data", "target_node_ids": ["main_data"]}
        else:
            payload = {"sql": initial_graph().data_nodes[0].sql}
        return SimpleNamespace(
            text=json.dumps(payload),
            model_version="test",
            usage_metadata=None,
            candidates=[],
        )


def test_production_scope_sql_state_and_offline_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise all 18 requests through production routing and repeat from cassettes."""
    monkeypatch.delenv("GEMINI_PROXY_URL", raising=False)
    monkeypatch.setattr("interactive_ehr.llm.gemini.load_dotenv", lambda: None)
    module = runner_module()
    inputs = tmp_path / "inputs"
    prepare(inputs)
    output = tmp_path / "run"
    output.mkdir()
    fake = FakeModels()
    recorder = module.RecordingModels(output, live=fake)
    events = module.run_sequences(inputs, output, recorder)
    assert len(events) == 18
    assert recorder.calls == len(fake.requests) == 36
    assert all(item["events"][-1]["status"] == "completed" for item in events)
    assert all(item["events"][0]["status"] == "started" for item in events)
    replay_output = tmp_path / "replay"
    replay_output.mkdir()
    replay = module.RecordingModels(replay_output, replay=output)
    assert module.run_sequences(inputs, replay_output, replay) == events
    assert len(replay.used_replay) == 36


def test_api_error_stops_without_retry_or_sensitive_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop all sequences after one failed request and redact transport details."""
    monkeypatch.setattr("interactive_ehr.llm.gemini.load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_PROXY_URL", raising=False)
    module = runner_module()
    inputs = tmp_path / "inputs"
    prepare(inputs)
    output = tmp_path / "run"
    output.mkdir()
    fake = FakeModels(fail=True)
    recorder = module.RecordingModels(output, live=fake)
    events = module.run_sequences(inputs, output, recorder)
    assert len(fake.requests) == 1
    assert len(events) == 1
    assert events[0]["events"][-1]["status"] == "failed"
    assert "secret URL" not in "".join(path.read_text() for path in output.iterdir())


def test_budget_blocks_call_before_transport(tmp_path: Path) -> None:
    """Enforce call and prompt bounds before billing any additional request."""
    module = runner_module()
    fake = FakeModels()
    recorder = module.RecordingModels(tmp_path, live=fake)
    with pytest.raises(RuntimeError, match="stopped_budget"):
        recorder.generate_content(
            model="test", contents="x" * (module.MAX_INPUT_BYTES + 1), config={}
        )
    assert not fake.requests
    assert recorder.calls == 0


def test_failed_update_skips_dependent_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop a sequence on malformed scope output while retaining the failed terminal state."""
    monkeypatch.setattr("interactive_ehr.llm.gemini.load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_PROXY_URL", raising=False)
    module = runner_module()
    inputs = tmp_path / "inputs"
    prepare(inputs)
    output = tmp_path / "run"
    output.mkdir()

    class Malformed:
        """Return syntactically valid JSON that violates the scope schema."""

        def generate_content(self, **kwargs: Any) -> Any:
            """Fail schema validation without a transport error or retry."""
            return SimpleNamespace(
                text="{}", model_version="test", usage_metadata=None, candidates=[]
            )

    recorder = module.RecordingModels(output, live=Malformed())
    events = module.run_sequences(inputs, output, recorder)
    assert len(events) == recorder.calls == 6
    assert all(item["id"].endswith("step_1") for item in events)
    summary = module.score(inputs, output)
    assert summary["n"] == 6
    assert len(summary["unattempted"]) == 12
    assert summary["pipeline_completed"] == 0


def test_changed_input_is_rejected(tmp_path: Path) -> None:
    """Reject a changed request before a run can touch network state."""
    module = runner_module()
    inputs = tmp_path / "inputs"
    prepare(inputs)
    save_json(inputs / "steps.json", [])
    with pytest.raises(ValueError, match="changed input"):
        module.verify_inputs(inputs)


def test_widget_route_uses_registered_fixture_and_production_attachment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the widget worker, normalizer, binding and SQL cache attachment."""
    monkeypatch.setattr("interactive_ehr.llm.gemini.load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_PROXY_URL", raising=False)
    module = runner_module()
    inputs = tmp_path / "inputs"
    prepare(inputs)
    # Bound this transport test to one step; live inputs remain 18 steps.
    steps = json.loads((inputs / "steps.json").read_text())
    save_json(inputs / "steps.json", steps[:1])
    output = tmp_path / "run"
    output.mkdir()

    class WidgetModels(FakeModels):
        """Return an existing widget with an intentionally wrong transient binding."""

        def generate_content(self, **kwargs: Any) -> Any:
            """Allow production normalization to restore the planned binding."""
            self.requests.append(kwargs)
            if len(self.requests) == 1:
                payload = {"scope": "widget", "target_node_ids": ["main"]}
            else:
                widget = initial_graph().widget_nodes[0].model_dump(mode="json")
                widget["widget"]["data_key"] = "transient_wrong_key"
                payload = {
                    "widget_node": widget,
                    "sql": initial_graph().data_nodes[0].sql,
                }
            return SimpleNamespace(
                text=json.dumps(payload),
                model_version="test",
                usage_metadata=None,
                candidates=[],
            )

    recorder = module.RecordingModels(output, live=WidgetModels())
    event = module.run_sequences(inputs, output, recorder)[0]["events"][-1]
    assert event["status"] == "completed"
    assert recorder.calls == 2
    assert event["graph"]["tasks"][0]["widgets"][0]["widget"]["data_key"] == "main_data"
    assert event["context"]["main_data"]["columns"] == ["observed_at", "value", "unit"]

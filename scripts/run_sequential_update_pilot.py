"""Record or replay a bounded run of the production ScenarioGraph updater."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
from threading import Lock
import time
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.oauth2 import service_account
import pandas as pd

from interactive_ehr import models, scenario_graph
from interactive_ehr.evaluation.generated_update_pilot import execute, save_json, sha256
from interactive_ehr.evaluation.sequential_update_pilot import (
    Step,
    SyntheticMeasurements,
    evaluate,
    pack_context,
    prepare,
)
from interactive_ehr.llm.gemini import GeminiMixin
from interactive_ehr.scenario_graph import ScenarioGraph

LOGGER = logging.getLogger(__name__)
EXPERIMENT = "experiments/chi-sequential-update-20260908"
SOURCE_FILES = [
    "scripts/run_sequential_update_pilot.py",
    "src/interactive_ehr/evaluation/sequential_update_pilot.py",
    "src/interactive_ehr/evaluation/generated_update_pilot.py",
    "src/interactive_ehr/scenario_graph.py",
    "src/interactive_ehr/app.py",
    "src/interactive_ehr/llm/gemini.py",
    "src/interactive_ehr/llm/schema_utils.py",
    "src/interactive_ehr/models/registry.py",
    "src/interactive_ehr/widgets/renderer.py",
    "src/interactive_ehr/widgets/chart.py",
    "src/interactive_ehr/widgets/display.py",
    "tests/test_sequential_update_pilot.py",
    "tests/test_sequential_update_runner.py",
    f"{EXPERIMENT}/PROTOCOL.md",
    "uv.lock",
]
CONFIG = {
    "temperature": 0.2,
    "top_p": 1.0,
    "max_output_tokens": 8192,
    "thinking_config": {"thinking_budget": 1024},
}
MAX_CALLS = 54
MAX_INPUT_BYTES = 120000
MAX_ESTIMATED_USD = 5.0


def timestamp() -> str:
    """Return an explicit UTC execution timestamp."""
    return datetime.now(timezone.utc).isoformat()


def verify_inputs(inputs: Path) -> None:
    """Refuse any input that changed after preparation."""
    for name, checksum in json.loads(
        (inputs / "input_manifest.json").read_text()
    ).items():
        if sha256(inputs / name) != checksum:
            raise ValueError(f"changed input: {name}")


class RecordingModels:
    """Wrap only SDK transport, preserving production prompts and JSON validation."""

    def __init__(
        self, destination: Path, live: Any | None = None, replay: Path | None = None
    ) -> None:
        """Create a fresh transcript destination and optional recorded source."""
        self.destination = destination
        self.live = live
        self.replay = replay
        self.lock = Lock()
        self.calls = 0
        self.reserved_usd = 0.0
        self.stop_reason: str | None = None
        self.step_id = ""
        self.records: list[dict[str, Any]] = []
        self.used_replay: set[str] = set()

    def generate_content(
        self, *, model: str, contents: str, config: dict[str, Any]
    ) -> Any:
        """Save each unchanged request/response, with no repair or automatic retry."""
        with self.lock:
            if self.stop_reason:
                raise RuntimeError(self.stop_reason)
            request = {"model": model, "contents": contents, "config": config}
            byte_count = len(json.dumps(request, ensure_ascii=False).encode())
            # UTF-8 bytes plus a schema/wrapper margin conservatively budget input tokens.
            cost = (byte_count + 2000) * 1.25 / 1_000_000 + 9216 * 10 / 1_000_000
            if (
                self.calls >= MAX_CALLS
                or byte_count > MAX_INPUT_BYTES
                or self.reserved_usd + cost > MAX_ESTIMATED_USD
            ):
                self.stop_reason = "stopped_budget"
                raise RuntimeError(self.stop_reason)
            self.calls += 1
            self.reserved_usd += cost
            name = f"call_{self.calls:03d}"
            settings = {**config, **CONFIG, "seed": 20260980 + self.calls}
            request["config"] = settings
            request_path = self.destination / f"{name}.request.json"
            save_json(request_path, request)
            record: dict[str, Any] = {
                "call": name,
                "step": self.step_id,
                "started_at": timestamp(),
                "request_sha256": sha256(request_path),
                "reserved_usd": cost,
            }
            started = time.perf_counter()
            if self.replay is not None:
                matches = []
                for path in self.replay.glob("call_*.request.json"):
                    saved = json.loads(path.read_text())
                    saved_metadata = json.loads(
                        path.with_name(
                            path.name.replace(".request.json", ".metadata.json")
                        ).read_text()
                    )
                    # Concurrent independent widgets may reach transport in a different order.
                    if (
                        saved["contents"] == contents
                        and saved_metadata["step"] == self.step_id
                        and saved["config"]["response_json_schema"]
                        == config["response_json_schema"]
                        and path.stem not in self.used_replay
                    ):
                        matches.append(path)
                if len(matches) != 1:
                    raise ValueError(
                        f"replay request mismatch: {name}, matches={len(matches)}"
                    )
                source = matches[0]
                self.used_replay.add(source.stem)
                old_name = source.name.replace(".request.json", "")
                metadata = json.loads(
                    (self.replay / f"{old_name}.metadata.json").read_text()
                )
                if metadata["status"] == "api_error":
                    self.stop_reason = "stopped_api_error"
                    raise RuntimeError(self.stop_reason)
                text = (self.replay / f"{old_name}.response.txt").read_text()
                response = SimpleNamespace(text=text)
                record.update({"status": "replayed", "replayed_call": old_name})
            else:
                try:
                    if self.live is None:
                        raise ValueError("live transport is missing")
                    response = self.live.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig.model_validate(settings),
                    )
                    text = response.text or ""
                    record.update(
                        {
                            "status": "returned",
                            "model_version": response.model_version,
                            "usage": response.usage_metadata.model_dump(mode="json")
                            if response.usage_metadata
                            else None,
                            "finish_reasons": [
                                str(candidate.finish_reason)
                                for candidate in response.candidates or []
                            ],
                        }
                    )
                except Exception as exc:
                    record.update(
                        {
                            "status": "api_error",
                            "error_type": type(exc).__name__,
                            "http_code": getattr(exc, "code", None),
                        }
                    )
                    record["elapsed_seconds"] = time.perf_counter() - started
                    save_json(self.destination / f"{name}.metadata.json", record)
                    self.records.append(record)
                    self.stop_reason = "stopped_api_error"
                    raise RuntimeError(f"api_error:{type(exc).__name__}") from None
            (self.destination / f"{name}.response.txt").write_text(
                text, encoding="utf-8"
            )
            record["response_sha256"] = sha256(
                self.destination / f"{name}.response.txt"
            )
            record["elapsed_seconds"] = time.perf_counter() - started
            save_json(self.destination / f"{name}.metadata.json", record)
            self.records.append(record)
            LOGGER.info("%s %s %s", self.step_id, name, record["status"])
            return response


def run_sequences(
    inputs: Path, destination: Path, recorder: RecordingModels
) -> list[dict[str, Any]]:
    """Run the unmodified scope decision and updater, continuing completed states only."""
    steps = [
        Step.model_validate(item)
        for item in json.loads((inputs / "steps.json").read_text())
    ]
    initial = ScenarioGraph.model_validate_json(
        (inputs / "initial_graph.json").read_text()
    )
    graph = initial
    context: dict[str, object] = {}
    events_by_step = []
    skip_sequence = False

    def execute_fixture(sql: str) -> pd.DataFrame:
        """Bind SQL execution to the restricted synthetic DB, never the user's DWH."""
        columns, rows = execute(sql, inputs / "state_0.sqlite")
        return pd.DataFrame(rows, columns=columns)

    def initialize_transport(instance: GeminiMixin) -> None:
        """Supply the recording client while retaining production generate/parsing."""
        instance._gemini_client = cast(Any, SimpleNamespace(models=recorder))
        instance._gemini_model = "gemini-2.5-pro"

    with (
        patch.object(GeminiMixin, "_init_gemini", initialize_transport),
        patch.object(scenario_graph, "execute_read_sql", execute_fixture),
        patch.object(models, "measurements", SyntheticMeasurements, create=True),
        patch.object(models, "__all__", [*models.__all__, "measurements"]),
    ):
        for step in steps:
            if recorder.stop_reason:
                break
            if step.index == 1:
                graph = initial.model_copy(deep=True)
                context = {
                    node.context_key: execute_fixture(node.sql or "")
                    for node in graph.data_nodes
                }
                skip_sequence = False
            if skip_sequence:
                continue
            recorder.step_id = step.id
            events = []
            before = {
                "graph": graph.model_dump(mode="json"),
                "context": pack_context(context),
            }
            start_call = recorder.calls
            for event in scenario_graph.update_scenario_graph_incrementally(
                (inputs / f"{step.id}.txt").read_text(), graph, context
            ):
                payload = {
                    "status": event.status,
                    "message": event.message,
                    "node_id": event.node_id,
                    "graph": event.graph.model_dump(mode="json"),
                    "context": pack_context(event.context),
                }
                events.append(payload)
                # The real app stores every yielded state, including a failed partial state.
                graph = event.graph
                context = event.context
            if not events:
                raise ValueError(f"updater emitted no event: {step.id}")
            record = {
                "id": step.id,
                "before": before,
                "events": events,
                "first_call": start_call + 1,
                "last_call": recorder.calls,
            }
            save_json(destination / f"{step.id}.events.json", record)
            events_by_step.append(record)
            skip_sequence = events[-1]["status"] != "completed"
            LOGGER.info("%s terminal=%s", step.id, events[-1]["status"])
    return events_by_step


def score(inputs: Path, output: Path) -> dict[str, Any]:
    """Evaluate saved terminal states and report paired decisions and sequence attrition."""
    verify_inputs(inputs)
    if (output / "candidate_results.jsonl").exists():
        raise FileExistsError("evaluation already exists")
    records = []
    missing = []
    first_invalid: dict[str, str] = {}
    for item in json.loads((inputs / "steps.json").read_text()):
        step = Step.model_validate(item)
        path = output / f"{step.id}.events.json"
        if not path.exists():
            missing.append(step.id)
            continue
        event = json.loads(path.read_text())["events"][-1]
        result = evaluate(step, event, inputs)
        result["prior_invalid_in_sequence"] = step.sequence in first_invalid
        if not result["audit_valid"] and step.sequence not in first_invalid:
            first_invalid[step.sequence] = step.id
        records.append(result)
    (output / "candidate_results.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    )
    summary = {
        "planned_steps": 18,
        "n": len(records),
        "unattempted": missing,
        "pipeline_completed": sum(record["pipeline_completed"] for record in records),
        "audit_valid": sum(record["audit_valid"] for record in records),
        "audit_invalid": sum(not record["audit_valid"] for record in records),
        "first_invalid_by_sequence": first_invalid,
        "conditions": {},
        "paired_disagreements": {},
    }
    for condition in ("structure", "simple_sql", "one_state", "three_states"):
        summary["conditions"][condition] = {
            "accepted": sum(record["accepted"][condition] for record in records),
            "invalid_accepted": sum(
                record["accepted"][condition] and not record["audit_valid"]
                for record in records
            ),
            "valid_rejected": sum(
                not record["accepted"][condition] and record["audit_valid"]
                for record in records
            ),
        }
    for left, right in [("simple_sql", "three_states"), ("one_state", "three_states")]:
        summary["paired_disagreements"][f"{left}_vs_{right}"] = [
            record["id"]
            for record in records
            if record["accepted"][left] != record["accepted"][right]
        ]
    save_json(output / "summary.json", summary)
    return summary


def run(inputs: Path, output: Path, replay: Path | None) -> int:
    """Freeze runtime provenance and execute one bounded live run or local replay."""
    verify_inputs(inputs)
    load_dotenv()
    if os.environ.get("GEMINI_PROXY_URL"):
        raise ValueError("the frozen transport requires Vertex, not proxy")
    if replay is None and os.environ.get("GEMINI_MODEL") != "gemini-2.5-pro":
        raise ValueError("configure GEMINI_MODEL=gemini-2.5-pro")
    sources = {name: sha256(Path(name)) for name in SOURCE_FILES}
    if replay is None:
        for name, checksum in sources.items():
            import hashlib

            if (
                hashlib.sha256(
                    subprocess.check_output(["git", "show", f"HEAD:{name}"])
                ).hexdigest()
                != checksum
            ):
                raise ValueError(f"source is not committed: {name}")
    else:
        frozen = json.loads((replay / "run_manifest.json").read_text())
        if sources != frozen["source_sha256"]:
            raise ValueError("replay source differs from frozen generation")
        for name, checksum in frozen["outputs_sha256"].items():
            if sha256(replay / name) != checksum:
                raise ValueError(f"changed output: {name}")
    output.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "started_at": timestamp(),
        "status": "running",
        "mode": "replay" if replay else "live",
        "model": "gemini-2.5-pro",
        "location": os.environ.get("GEMINI_LOCATION"),
        "config": CONFIG,
        "seed_base": 20260980,
        "max_calls": MAX_CALLS,
        "max_input_bytes": MAX_INPUT_BYTES,
        "max_estimated_usd": MAX_ESTIMATED_USD,
        "timeout_ms": 120000,
        "attempts": 1,
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_sha256": sources,
        "input_manifest_sha256": sha256(inputs / "input_manifest.json"),
        "python": platform.python_version(),
        "google_genai": importlib.metadata.version("google-genai"),
    }
    save_json(output / "run_manifest.json", manifest)
    client = None
    if replay is None:
        credentials = service_account.Credentials.from_service_account_file(
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        ).with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
        client = genai.Client(
            vertexai=True,
            project=os.environ["GEMINI_PROJECT"],
            location=os.environ["GEMINI_LOCATION"],
            credentials=credentials,
            http_options=types.HttpOptions(
                timeout=120000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
    recorder = RecordingModels(
        output, live=client.models if client else None, replay=replay
    )
    try:
        events = run_sequences(inputs, output, recorder)
        manifest["status"] = recorder.stop_reason or "completed"
        manifest["attempted_steps"] = [event["id"] for event in events]
        if replay:
            for event in events:
                saved = json.loads((replay / f"{event['id']}.events.json").read_text())
                if event != saved:
                    raise ValueError(f"pipeline replay differs: {event['id']}")
            manifest["all_events_match"] = True
    except Exception:
        manifest["status"] = "aborted_unhandled"
        raise
    finally:
        if client:
            client.close()
        manifest["finished_at"] = timestamp()
        manifest["calls"] = recorder.calls
        manifest["reserved_usd"] = recorder.reserved_usd
        usage: Counter[str] = Counter()
        for record in recorder.records:
            for key, value in (record.get("usage") or {}).items():
                if isinstance(value, int):
                    usage[key] += value
        manifest["usage"] = dict(usage)
        manifest["outputs_sha256"] = {
            path.name: sha256(path)
            for path in sorted(output.iterdir())
            if path.name != "run_manifest.json"
        }
        save_json(output / "run_manifest.json", manifest)
    return 0 if manifest["status"] == "completed" else 2


def main() -> int:
    """Dispatch preparation, generation, scoring or deterministic offline replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "generate", "score", "replay"])
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replay-source", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.action == "prepare":
        prepare(args.inputs)
        return 0
    if args.output is None:
        parser.error("--output is required")
    if args.action == "score":
        LOGGER.info("%s", score(args.inputs, args.output))
        return 0
    if args.action == "replay" and args.replay_source is None:
        parser.error("--replay-source is required")
    return run(
        args.inputs,
        args.output,
        args.replay_source if args.action == "replay" else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())

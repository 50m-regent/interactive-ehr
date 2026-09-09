"""Prepare, generate and score the bounded synthetic CHI update pilot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.oauth2 import service_account

from interactive_ehr.evaluation.generated_update_pilot import (
    Case,
    Interface,
    evaluate,
    prepare_inputs,
    save_json,
    sha256,
    summarize,
)
from interactive_ehr.llm.schema_utils import to_gemini_response_json_schema

LOGGER = logging.getLogger(__name__)
SOURCE_FILES = [
    "src/interactive_ehr/evaluation/generated_update_pilot.py",
    "scripts/run_generated_update_pilot.py",
    "tests/test_generated_update_pilot.py",
    "tests/test_generated_update_runner.py",
    "src/interactive_ehr/widgets/renderer.py",
    "src/interactive_ehr/widgets/chart.py",
    "src/interactive_ehr/widgets/display.py",
    "src/interactive_ehr/llm/schema_utils.py",
    "experiments/chi-generated-update-20260908/PROTOCOL.md",
    "uv.lock",
]


def timestamp() -> str:
    """Return an explicit UTC timestamp for each execution stage."""
    return datetime.now(timezone.utc).isoformat()


def verify_inputs(inputs: Path) -> None:
    """Reject changed inputs before network access or evaluation."""
    expected = json.loads((inputs / "input_manifest.json").read_text())
    for name, checksum in expected.items():
        if sha256(inputs / name) != checksum:
            raise ValueError(f"input checksum mismatch: {name}")


def generate(inputs: Path, output: Path) -> int:
    """Call the configured Vertex model once per case with no automatic retries."""
    verify_inputs(inputs)
    load_dotenv()
    model = os.environ.get("GEMINI_MODEL")
    if model != "gemini-2.5-pro" or os.environ.get("GEMINI_PROXY_URL"):
        raise ValueError(
            "This frozen protocol requires configured Vertex gemini-2.5-pro"
        )
    credential_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    credentials = service_account.Credentials.from_service_account_file(
        credential_path
    ).with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
    cases = [
        Case.model_validate(item)
        for item in json.loads((inputs / "cases.json").read_text())
    ]
    if len(cases) != 20:
        raise ValueError("The generation budget is exactly 20 planned cases")
    schema = to_gemini_response_json_schema(Interface.model_json_schema())
    for case in cases:
        prompt = (inputs / f"{case.id}.txt").read_text()
        if len(prompt.encode()) + len(json.dumps(schema).encode()) > 20000:
            raise ValueError("input byte budget exceeded")
    output.mkdir(parents=True, exist_ok=False)
    config = {
        "temperature": 0.2,
        "top_p": 1.0,
        "max_output_tokens": 4096,
        "thinking_config": {"thinking_budget": 1024},
        "response_mime_type": "application/json",
        "response_json_schema": schema,
    }
    manifest: dict[str, Any] = {
        "started_at": timestamp(),
        "status": "running",
        "model_requested": model,
        "location": os.environ.get("GEMINI_LOCATION"),
        "planned_cases": 20,
        "seed_base": 20260908,
        "config": config,
        "timeout_ms": 120000,
        "attempts": 1,
        "input_manifest_sha256": sha256(inputs / "input_manifest.json"),
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_sha256": {name: sha256(Path(name)) for name in SOURCE_FILES},
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "google_genai": importlib.metadata.version("google-genai"),
        "completed_cases": [],
        "unattempted_cases": [case.id for case in cases],
    }
    save_json(output / "run_manifest.json", manifest)
    with genai.Client(
        vertexai=True,
        project=os.environ["GEMINI_PROJECT"],
        location=os.environ["GEMINI_LOCATION"],
        credentials=credentials,
        http_options=types.HttpOptions(
            timeout=120000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    ) as client:
        for index, case in enumerate(cases):
            started = time.perf_counter()
            record: dict[str, Any] = {
                "id": case.id,
                "started_at": timestamp(),
                "seed": 20260908 + index,
            }
            LOGGER.info("Generating %s (%s/20)", case.id, index + 1)
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=(inputs / f"{case.id}.txt").read_text(),
                    config=types.GenerateContentConfig.model_validate(
                        {**config, "seed": 20260908 + index}
                    ),
                )
                text = response.text or ""
                (output / f"{case.id}.txt").write_text(text, encoding="utf-8")
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
                        "text_sha256": sha256(output / f"{case.id}.txt"),
                    }
                )
            except Exception as exc:
                # Do not persist exception strings that may contain credential paths or request URLs.
                record.update(
                    {
                        "status": "api_error",
                        "error_type": type(exc).__name__,
                        "http_code": getattr(exc, "code", None),
                    }
                )
                LOGGER.error(
                    "Stopped on %s: %s code=%s; no retry",
                    case.id,
                    type(exc).__name__,
                    getattr(exc, "code", None),
                )
            record["elapsed_seconds"] = time.perf_counter() - started
            save_json(output / f"{case.id}.metadata.json", record)
            manifest["completed_cases"].append(case.id)
            manifest["unattempted_cases"].remove(case.id)
            if record["status"] == "api_error":
                manifest["status"] = "stopped_api_error"
                break
            save_json(output / "run_manifest.json", manifest)
    if (
        len(manifest["completed_cases"]) == 20
        and manifest["status"] != "stopped_api_error"
    ):
        manifest["status"] = "completed"
    manifest["finished_at"] = timestamp()
    manifest["outputs_sha256"] = {
        path.name: sha256(path)
        for path in sorted(output.iterdir())
        if path.name != "run_manifest.json"
    }
    save_json(output / "run_manifest.json", manifest)
    return 0 if manifest["status"] == "completed" else 2


def score(inputs: Path, output: Path) -> None:
    """Evaluate each attempted response and retain unavailable cases separately."""
    verify_inputs(inputs)
    if (output / "candidate_results.jsonl").exists():
        raise FileExistsError(
            "Evaluation already exists; use a separate output directory"
        )
    records = []
    missing = []
    for item in json.loads((inputs / "cases.json").read_text()):
        case = Case.model_validate(item)
        response = output / f"{case.id}.txt"
        if not response.exists():
            missing.append(case.id)
            continue
        record = evaluate(case, response.read_text(), inputs)
        record["response_sha256"] = sha256(response)
        records.append(record)
    (output / "candidate_results.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    summary = summarize(records)
    summary.update(
        {
            "planned": 20,
            "unavailable": missing,
            "label_scope": "finite held-out synthetic executions and explicit display policy; no expert labels",
        }
    )
    save_json(output / "summary.json", summary)
    save_json(
        output / "evaluation_manifest.json",
        {
            "evaluated_at": timestamp(),
            "source_sha256": {name: sha256(Path(name)) for name in SOURCE_FILES},
            "input_manifest_sha256": sha256(inputs / "input_manifest.json"),
            "outputs_sha256": {
                name: sha256(output / name)
                for name in ("candidate_results.jsonl", "summary.json")
            },
        },
    )
    LOGGER.info("Evaluated %s outputs; %s unavailable", len(records), len(missing))


def main() -> int:
    """Dispatch explicit preparation, generation or local scoring stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "generate", "score"])
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.action == "prepare":
        prepare_inputs(args.inputs)
        return 0
    if args.output is None:
        parser.error("--output is required for generate and score")
    if args.action == "generate":
        return generate(args.inputs, args.output)
    score(args.inputs, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

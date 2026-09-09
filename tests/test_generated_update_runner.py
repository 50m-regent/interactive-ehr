"""Test the API budget, checkpointing and stop policy using a mock client."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from interactive_ehr.evaluation.generated_update_pilot import prepare_inputs


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, MagicMock]:
    """Load the CLI module with all credentials and network access mocked."""
    spec = importlib.util.spec_from_file_location(
        "pilot_runner", "scripts/run_generated_update_pilot.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_PROJECT", "mock-project")
    monkeypatch.setenv("GEMINI_LOCATION", "mock-location")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "not-a-real-key")
    monkeypatch.delenv("GEMINI_PROXY_URL", raising=False)
    monkeypatch.setattr(
        module.service_account.Credentials, "from_service_account_file", MagicMock()
    )
    client_class = MagicMock()
    monkeypatch.setattr(module.genai, "Client", client_class)
    return module, client_class


def test_generation_calls_exactly_twenty_without_retries(
    tmp_path: Path, runner: tuple[ModuleType, MagicMock]
) -> None:
    """Record all planned responses with bounded settings and SDK retry disabled."""
    module, client_class = runner
    inputs, output = tmp_path / "inputs", tmp_path / "output"
    prepare_inputs(inputs)
    response = MagicMock(
        text="{}", model_version="mock-version", usage_metadata=None, candidates=[]
    )
    generate = client_class.return_value.__enter__.return_value.models.generate_content
    generate.return_value = response
    assert module.generate(inputs, output) == 0
    assert generate.call_count == 20
    assert client_class.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert all(
        call.kwargs["config"].max_output_tokens == 4096
        for call in generate.call_args_list
    )
    assert (
        json.loads((output / "run_manifest.json").read_text())["status"] == "completed"
    )


def test_api_error_stops_and_does_not_leak_exception(
    tmp_path: Path, runner: tuple[ModuleType, MagicMock]
) -> None:
    """Stop after one failed request and retain the 19 unattempted cases separately."""
    module, client_class = runner
    inputs, output = tmp_path / "inputs", tmp_path / "output"
    prepare_inputs(inputs)
    generate = client_class.return_value.__enter__.return_value.models.generate_content
    generate.side_effect = RuntimeError("sensitive-example-do-not-store")
    assert module.generate(inputs, output) == 2
    assert generate.call_count == 1
    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["status"] == "stopped_api_error"
    assert len(manifest["unattempted_cases"]) == 19
    assert "sensitive-example" not in (output / "update_01.metadata.json").read_text()


def test_modified_input_prevents_network_call(
    tmp_path: Path, runner: tuple[ModuleType, MagicMock]
) -> None:
    """Detect prompt edits before opening the generation client."""
    module, client_class = runner
    inputs = tmp_path / "inputs"
    prepare_inputs(inputs)
    (inputs / "update_01.txt").write_text("changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        module.generate(inputs, tmp_path / "output")
    client_class.assert_not_called()

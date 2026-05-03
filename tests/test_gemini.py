"""GeminiMixin のテスト."""

from __future__ import annotations

import json
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from interactive_ehr.llm.gemini import (
    DEFAULT_LOCATION,
    DEFAULT_MODEL,
    DEFAULT_PROJECT,
    GeminiMixin,
)


class SampleResponse(BaseModel):
    """テスト用のレスポンススキーマ."""

    message: str
    count: int


class _Client(GeminiMixin):
    """GeminiMixinを利用する具象クラス."""


@pytest.fixture
def mock_genai_client() -> Generator[MagicMock, None, None]:
    """genai.Client をモック."""
    with patch("interactive_ehr.llm.gemini.genai.Client") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield mock_cls


@pytest.fixture
def mock_credentials() -> Generator[MagicMock, None, None]:
    """service_account.Credentials をモック."""
    with patch(
        "interactive_ehr.llm.gemini.service_account.Credentials"
    ) as mock_cls:
        mock_cls.from_service_account_file.return_value.with_scopes.return_value = (
            MagicMock()
        )
        yield mock_cls


def _make_response(text: str) -> MagicMock:
    """generate_content のレスポンスをモック."""
    response = MagicMock()
    response.text = text
    return response


class TestInit:
    def test_missing_credentials_env_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        client = _Client()
        with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
            client.generate("hello", SampleResponse)

    def test_uses_default_project_location_model(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        monkeypatch.delenv("GEMINI_PROJECT", raising=False)
        monkeypatch.delenv("GEMINI_LOCATION", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)

        client = _Client()
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response('{"message": "hi", "count": 1}')
        )
        client.generate("hello", SampleResponse)

        mock_genai_client.assert_called_once()
        kwargs = mock_genai_client.call_args.kwargs
        assert kwargs["vertexai"] is True
        assert kwargs["project"] == DEFAULT_PROJECT
        assert kwargs["location"] == DEFAULT_LOCATION

        call_kwargs = (
            mock_genai_client.return_value.models.generate_content.call_args.kwargs
        )
        assert call_kwargs["model"] == DEFAULT_MODEL

    def test_env_overrides_are_applied(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        monkeypatch.setenv("GEMINI_PROJECT", "my-project")
        monkeypatch.setenv("GEMINI_LOCATION", "us-central1")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

        client = _Client()
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response('{"message": "hi", "count": 1}')
        )
        client.generate("hello", SampleResponse)

        kwargs = mock_genai_client.call_args.kwargs
        assert kwargs["project"] == "my-project"
        assert kwargs["location"] == "us-central1"
        call_kwargs = (
            mock_genai_client.return_value.models.generate_content.call_args.kwargs
        )
        assert call_kwargs["model"] == "gemini-2.5-flash"

    def test_client_is_lazily_initialized_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        client = _Client()
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response('{"message": "hi", "count": 1}')
        )
        client.generate("1st", SampleResponse)
        client.generate("2nd", SampleResponse)
        assert mock_genai_client.call_count == 1


class TestGenerate:
    def test_parses_structured_json_into_pydantic_model(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response('{"message": "ok", "count": 42}')
        )
        client = _Client()
        result = client.generate("prompt", SampleResponse)
        assert isinstance(result, SampleResponse)
        assert result.message == "ok"
        assert result.count == 42

    def test_passes_schema_to_generate_content(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response('{"message": "ok", "count": 1}')
        )
        client = _Client()
        client.generate("prompt", SampleResponse)

        call_kwargs = (
            mock_genai_client.return_value.models.generate_content.call_args.kwargs
        )
        assert call_kwargs["contents"] == "prompt"
        assert call_kwargs["config"]["response_mime_type"] == "application/json"
        assert (
            call_kwargs["config"]["response_schema"]
            == SampleResponse.model_json_schema()
        )

    def test_invalid_json_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response("not json")
        )
        client = _Client()
        with pytest.raises(json.JSONDecodeError):
            client.generate("prompt", SampleResponse)

    def test_missing_text_attribute_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        response = MagicMock(spec=[])  # text属性なし
        mock_genai_client.return_value.models.generate_content.return_value = response
        client = _Client()
        with pytest.raises(ValueError, match="text属性"):
            client.generate("prompt", SampleResponse)

    def test_schema_validation_error_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response('{"message": "ok"}')
        )
        client = _Client()
        with pytest.raises(ValidationError):
            client.generate("prompt", SampleResponse)

    def test_empty_response_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_genai_client: MagicMock,
        mock_credentials: MagicMock,
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        mock_genai_client.return_value.models.generate_content.return_value = (
            _make_response("   ")
        )
        client = _Client()
        with pytest.raises(ValueError, match="空"):
            client.generate("prompt", SampleResponse)

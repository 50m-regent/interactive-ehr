"""閉域プロキシバックエンド (gemini_proxy) のテスト."""

from __future__ import annotations

import json
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import BaseModel, ValidationError

from interactive_ehr.llm.gemini import GeminiMixin
from interactive_ehr.llm.gemini_proxy import (
    DEFAULT_PROXY_MODEL,
    ProxyConfig,
    generate_via_proxy,
)
from interactive_ehr.llm.schema_utils import to_gemini_response_json_schema

PROXY_URL = "http://gemini-proxy.example:3000/api/gemini"


class SampleResponse(BaseModel):
    """テスト用のレスポンススキーマ."""

    message: str
    count: int


class _Client(GeminiMixin):
    """GeminiMixinを利用する具象クラス."""


@pytest.fixture(autouse=True)
def clean_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """各テストが実際の環境変数・.envに依存しないようにする."""
    for name in (
        "GEMINI_PROXY_URL",
        "GEMINI_MODEL",
        "GEMINI_PROXY_MAX_OUTPUT_TOKENS",
        "GEMINI_PROXY_TEMPERATURE",
        "GEMINI_PROXY_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("interactive_ehr.llm.gemini.load_dotenv", MagicMock())


@pytest.fixture
def mock_post() -> Generator[MagicMock, None, None]:
    """requests.post をモック."""
    with patch("interactive_ehr.llm.gemini_proxy.requests.post") as mock:
        yield mock


def _make_response(text: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response


def _config(**overrides: object) -> ProxyConfig:
    params: dict[str, object] = {"url": PROXY_URL}
    params.update(overrides)
    return ProxyConfig(**params)  # type: ignore[arg-type]


class TestProxyConfig:
    def test_from_env_returns_none_without_url(self) -> None:
        assert ProxyConfig.from_env() is None

    def test_from_env_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_PROXY_URL", PROXY_URL)
        config = ProxyConfig.from_env()
        assert config is not None
        assert config.url == PROXY_URL
        assert config.model == DEFAULT_PROXY_MODEL
        assert config.model == "gemini-2.5-flash-lite"
        assert config.max_output_tokens == 8192
        assert config.temperature == 0.2
        assert config.timeout_seconds == 300.0

    def test_from_env_applies_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_PROXY_URL", PROXY_URL)
        monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro")
        monkeypatch.setenv("GEMINI_PROXY_MAX_OUTPUT_TOKENS", "32768")
        monkeypatch.setenv("GEMINI_PROXY_TEMPERATURE", "0.7")
        monkeypatch.setenv("GEMINI_PROXY_TIMEOUT", "60")
        config = ProxyConfig.from_env()
        assert config is not None
        assert config.model == "gemini-3.1-pro"
        assert config.max_output_tokens == 32768
        assert config.temperature == 0.7
        assert config.timeout_seconds == 60.0

    def test_from_env_invalid_number_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_PROXY_URL", PROXY_URL)
        monkeypatch.setenv("GEMINI_PROXY_MAX_OUTPUT_TOKENS", "たくさん")
        with pytest.raises(ValueError, match="GEMINI_PROXY_MAX_OUTPUT_TOKENS"):
            ProxyConfig.from_env()


class TestGenerateViaProxy:
    def test_sends_expected_payload(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _make_response('{"message": "ok", "count": 1}')
        generate_via_proxy("こんにちは", SampleResponse, _config())

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == PROXY_URL
        payload = kwargs["json"]
        assert payload["jsonMode"] is True
        assert payload["model"] == DEFAULT_PROXY_MODEL
        assert payload["maxOutputTokens"] == 8192
        assert payload["temperature"] == 0.2
        assert kwargs["timeout"] == 300.0

    def test_prompt_and_schema_are_embedded_in_input(
        self, mock_post: MagicMock
    ) -> None:
        mock_post.return_value = _make_response('{"message": "ok", "count": 1}')
        generate_via_proxy("プロンプト本文", SampleResponse, _config())

        input_text = mock_post.call_args.kwargs["json"]["input"]
        assert "プロンプト本文" in input_text
        schema_json = json.dumps(
            to_gemini_response_json_schema(SampleResponse.model_json_schema()),
            ensure_ascii=False,
        )
        assert schema_json in input_text

    def test_parses_json_into_pydantic_model(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _make_response('{"message": "ok", "count": 42}')
        result = generate_via_proxy("prompt", SampleResponse, _config())
        assert isinstance(result, SampleResponse)
        assert result.message == "ok"
        assert result.count == 42

    def test_strips_json_code_fence(self, mock_post: MagicMock) -> None:
        fenced = '```json\n{"message": "ok", "count": 7}\n```'
        mock_post.return_value = _make_response(fenced)
        result = generate_via_proxy("prompt", SampleResponse, _config())
        assert result.count == 7

    def test_non_200_raises_runtime_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _make_response(
            '{"error": true, "statusCode": 400, "message": "Invalid request body"}',
            status_code=400,
        )
        with pytest.raises(RuntimeError, match="400"):
            generate_via_proxy("prompt", SampleResponse, _config())

    def test_error_body_with_200_raises_runtime_error(
        self, mock_post: MagicMock
    ) -> None:
        mock_post.return_value = _make_response(
            '{"error": true, "statusCode": 500, "message": "internal"}'
        )
        with pytest.raises(RuntimeError, match="エラー"):
            generate_via_proxy("prompt", SampleResponse, _config())

    def test_invalid_json_raises(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _make_response("not json")
        with pytest.raises(json.JSONDecodeError):
            generate_via_proxy("prompt", SampleResponse, _config())

    def test_empty_response_raises(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _make_response("   ")
        with pytest.raises(ValueError, match="空"):
            generate_via_proxy("prompt", SampleResponse, _config())

    def test_timeout_raises_actionable_runtime_error(
        self, mock_post: MagicMock
    ) -> None:
        """タイムアウト時にモデルと確認項目を示す."""

        mock_post.side_effect = requests.Timeout("read timed out")

        with pytest.raises(RuntimeError, match="gemini-2.5-flash-lite.*300秒"):
            generate_via_proxy("prompt", SampleResponse, _config())

    def test_connection_error_raises_actionable_runtime_error(
        self, mock_post: MagicMock
    ) -> None:
        """接続失敗時にURLとコンテナ疎通の確認を促す."""

        mock_post.side_effect = requests.ConnectionError("connection refused")

        with pytest.raises(RuntimeError, match="GEMINI_PROXY_URL"):
            generate_via_proxy("prompt", SampleResponse, _config())

    def test_schema_validation_error_raises(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _make_response('{"message": "ok"}')
        with pytest.raises(ValidationError):
            generate_via_proxy("prompt", SampleResponse, _config())


class TestGeminiMixinRouting:
    def test_routes_to_proxy_when_env_is_set(
        self, monkeypatch: pytest.MonkeyPatch, mock_post: MagicMock
    ) -> None:
        monkeypatch.setenv("GEMINI_PROXY_URL", PROXY_URL)
        mock_post.return_value = _make_response('{"message": "ok", "count": 1}')

        with patch("interactive_ehr.llm.gemini.genai.Client") as mock_genai:
            client = _Client()
            result = client.generate("prompt", SampleResponse)

        assert result.message == "ok"
        mock_post.assert_called_once()
        mock_genai.assert_not_called()

    def test_vertex_path_is_used_without_proxy_env(
        self, monkeypatch: pytest.MonkeyPatch, mock_post: MagicMock
    ) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json")
        with (
            patch("interactive_ehr.llm.gemini.genai.Client") as mock_genai,
            patch("interactive_ehr.llm.gemini.service_account.Credentials"),
        ):
            response = MagicMock()
            response.text = '{"message": "ok", "count": 1}'
            mock_genai.return_value.models.generate_content.return_value = response
            client = _Client()
            result = client.generate("prompt", SampleResponse)

        assert result.count == 1
        mock_post.assert_not_called()
        mock_genai.assert_called_once()

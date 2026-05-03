"""Gemini API連携用のmixinクラス.

Vertex AI経由でGemini APIを呼び出し、Pydanticスキーマに基づく構造化出力を返す。

環境変数:
    GOOGLE_APPLICATION_CREDENTIALS: サービスアカウントJSONファイルへのパス (必須)
    GEMINI_PROJECT: GCPプロジェクトID (デフォルト: gemini-api-project-464304)
    GEMINI_LOCATION: Vertex AIロケーション (デフォルト: asia-northeast1)
    GEMINI_MODEL: Geminiモデル名 (デフォルト: gemini-2.5-pro)
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
import os
from typing import TYPE_CHECKING, Any, TypeVar

from google import genai
from google.oauth2 import service_account
from dotenv import load_dotenv
from pydantic import BaseModel

if TYPE_CHECKING:
    from google.genai.client import Client

T = TypeVar("T", bound=BaseModel)

DEFAULT_PROJECT = "gemini-api-project-464304"
DEFAULT_LOCATION = "asia-northeast1"
DEFAULT_MODEL = "gemini-2.5-pro"

_CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_GEMINI_JSON_SCHEMA_KEYS = {
    "$anchor",
    "$defs",
    "$id",
    "$ref",
    "additionalProperties",
    "anyOf",
    "description",
    "enum",
    "format",
    "items",
    "maxItems",
    "maximum",
    "minItems",
    "minimum",
    "oneOf",
    "prefixItems",
    "properties",
    "propertyOrdering",
    "required",
    "title",
    "type",
}


class GeminiMixin:
    """Gemini APIの構造化出力生成機能を提供するmixin.

    クライアントは初回 `generate` 呼び出し時に lazy 初期化される。
    他のmixinとの属性衝突を避けるため、内部状態は `_gemini_` プレフィックス。
    """

    _gemini_client: Client | None
    _gemini_model: str | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        # mixinなので super() を呼んで多重継承チェーンを維持
        super().__init__(*args, **kwargs)
        self._gemini_client = None
        self._gemini_model = None

    def _init_gemini(self) -> None:
        """Geminiクライアントを初期化."""
        load_dotenv()
        credentials_path = os.environ.get(_CREDENTIALS_ENV)
        if not credentials_path:
            raise RuntimeError(
                f"環境変数 {_CREDENTIALS_ENV} が設定されていません。"
                "サービスアカウントJSONファイルへのパスを指定してください。"
            )

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        ).with_scopes(_SCOPES)

        self._gemini_client = genai.Client(
            vertexai=True,
            project=os.environ.get("GEMINI_PROJECT", DEFAULT_PROJECT),
            location=os.environ.get("GEMINI_LOCATION", DEFAULT_LOCATION),
            credentials=credentials,
        )
        self._gemini_model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    def generate(self, prompt: str, schema: type[T]) -> T:
        """プロンプトを投げて構造化レスポンス（Pydanticモデル）を返す.

        Args:
            prompt: Geminiへの入力プロンプト
            schema: レスポンスをパースするPydanticモデル

        Returns:
            schema でパースされたPydanticモデルインスタンス

        Raises:
            RuntimeError: 認証情報が未設定
            ValueError: レスポンスのJSONパース失敗
            pydantic.ValidationError: スキーマ検証失敗
        """
        if self._gemini_client is None:
            self._init_gemini()

        client = self._gemini_client
        model = self._gemini_model
        if client is None or model is None:
            raise RuntimeError("Geminiクライアントの初期化に失敗しました。")

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": _to_gemini_response_json_schema(
                    schema.model_json_schema()
                ),
            },
        )

        response_text = _extract_text(response)
        json_data = json.loads(response_text)
        return schema.model_validate(json_data)


def _extract_text(response: object) -> str:
    """Geminiレスポンスからテキスト部分を抽出."""
    text = getattr(response, "text", None)
    if text is None:
        raise ValueError(f"Geminiレスポンスにtext属性がありません: {response!r}")
    stripped = text.strip()
    if not stripped:
        raise ValueError("Geminiレスポンスが空です")
    return stripped


def _to_gemini_response_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Convert Pydantic JSON Schema to the subset accepted by Gemini."""
    return _sanitize_json_schema_node(deepcopy(dict(schema)))


def _sanitize_json_schema_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitize_json_schema_node(item) for item in node]
    if not isinstance(node, dict):
        return node

    sanitized: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"$defs", "properties"}:
            sanitized[key] = {
                name: _sanitize_json_schema_node(child)
                for name, child in value.items()
            }
            continue
        if key == "const":
            sanitized["enum"] = [value]
            continue
        if key not in _GEMINI_JSON_SCHEMA_KEYS:
            continue
        sanitized[key] = _sanitize_json_schema_node(value)
    return sanitized

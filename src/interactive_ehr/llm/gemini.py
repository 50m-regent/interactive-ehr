"""Gemini API連携用のmixinクラス.

デフォルトでは Vertex AI 経由で Gemini API を呼び出し、Pydanticスキーマに
基づく構造化出力を返す。環境変数 GEMINI_PROXY_URL が設定されている場合は、
閉域ネットワーク向けのベンダー提供プロキシ (`gemini_proxy` モジュール) に
切り替わる。

環境変数:
    GEMINI_PROXY_URL: 閉域プロキシのURL (設定するとプロキシモードに切替)
    GOOGLE_APPLICATION_CREDENTIALS: サービスアカウントJSONファイルへのパス
        (Vertex AIモードで必須)
    GEMINI_PROJECT: GCPプロジェクトID (デフォルト: gemini-api-project-464304)
    GEMINI_LOCATION: Vertex AIロケーション (デフォルト: asia-northeast1)
    GEMINI_MODEL: Geminiモデル名 (デフォルト: gemini-2.5-pro、
        プロキシモードでは gemini-2.5-flash-lite)

プロキシモード固有の環境変数は `gemini_proxy` モジュールを参照。
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from typing import TYPE_CHECKING, Any, TypeVar

from google import genai
from google.oauth2 import service_account
from dotenv import load_dotenv
from pydantic import BaseModel

from interactive_ehr.llm.gemini_proxy import ProxyConfig, generate_via_proxy
from interactive_ehr.llm.schema_utils import to_gemini_response_json_schema

if TYPE_CHECKING:
    from google.genai.client import Client

T = TypeVar("T", bound=BaseModel)

DEFAULT_PROJECT = "gemini-api-project-464304"
DEFAULT_LOCATION = "asia-northeast1"
DEFAULT_MODEL = "gemini-2.5-pro"

_CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


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
        """Vertex AI用のGeminiクライアントを初期化."""
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
            RuntimeError: 認証情報が未設定、またはプロキシがエラーを返した
            ValueError: レスポンスのJSONパース失敗
            pydantic.ValidationError: スキーマ検証失敗
        """
        load_dotenv()

        proxy_config = ProxyConfig.from_env()
        if proxy_config is not None:
            return generate_via_proxy(prompt, schema, proxy_config)

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
    """Convert Pydantic JSON Schema to the subset accepted by Gemini.

    実体は `schema_utils.to_gemini_response_json_schema`（プロキシバックエンドと
    共用）。既存の利用箇所・テストとの互換のためこの名前を維持している。
    """
    return to_gemini_response_json_schema(schema)

"""閉域ネットワーク向けベンダー提供Geminiプロキシのバックエンド.

Vertex AI に到達できない閉域環境では、ベンダー提供のHTTPプロキシ経由で
Gemini を呼び出す。プロキシは認証なしのPOSTを受け付け、リクエストbodyは
`{"model", "maxOutputTokens", "temperature", "input", "jsonMode"}` 形式。
`jsonMode` は必須（未指定だとHTTP 400）。レスポンスbodyがそのまま生成テキスト。

プロキシには構造化出力（JSON Schema指定）の機能がないため、スキーマは
プロンプト文中に埋め込み、返却されたJSONをPydanticで検証する。

環境変数:
    GEMINI_PROXY_URL: プロキシのURL (設定されているとプロキシモードになる)
    GEMINI_MODEL: モデル名 (デフォルト: gemini-2.5-flash-lite)
    GEMINI_PROXY_MAX_OUTPUT_TOKENS: 最大出力トークン数 (デフォルト: 8192)
    GEMINI_PROXY_TEMPERATURE: 温度 (デフォルト: 0.2)
    GEMINI_PROXY_TIMEOUT: リクエストタイムアウト秒 (デフォルト: 300)
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import TypeVar

import requests
from pydantic import BaseModel

from interactive_ehr.llm.schema_utils import to_gemini_response_json_schema

T = TypeVar("T", bound=BaseModel)

PROXY_URL_ENV = "GEMINI_PROXY_URL"
DEFAULT_PROXY_MODEL = "gemini-2.5-flash-lite"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_SECONDS = 300.0

_SCHEMA_INSTRUCTION = """

# 出力形式（厳守）

出力は、以下のJSON Schemaに厳密に従う単一のJSONオブジェクトのみとしてください。
説明文・前置き・コードフェンス（```）は一切含めないでください。

## JSON Schema

{schema_json}
"""


@dataclass(frozen=True)
class ProxyConfig:
    """プロキシ接続設定."""

    url: str
    model: str = DEFAULT_PROXY_MODEL
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> ProxyConfig | None:
        """環境変数から設定を構築する. GEMINI_PROXY_URL 未設定なら None."""
        url = os.environ.get(PROXY_URL_ENV)
        if not url:
            return None
        return cls(
            url=url,
            model=os.environ.get("GEMINI_MODEL", DEFAULT_PROXY_MODEL),
            max_output_tokens=_int_env(
                "GEMINI_PROXY_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS
            ),
            temperature=_float_env(
                "GEMINI_PROXY_TEMPERATURE", DEFAULT_TEMPERATURE
            ),
            timeout_seconds=_float_env(
                "GEMINI_PROXY_TIMEOUT", DEFAULT_TIMEOUT_SECONDS
            ),
        )


def generate_via_proxy(prompt: str, schema: type[T], config: ProxyConfig) -> T:
    """プロキシ経由でプロンプトを投げ、構造化レスポンスを返す.

    Args:
        prompt: Geminiへの入力プロンプト
        schema: レスポンスをパースするPydanticモデル
        config: プロキシ接続設定

    Returns:
        schema でパースされたPydanticモデルインスタンス

    Raises:
        RuntimeError: プロキシがHTTPエラーまたはエラーbodyを返した
        ValueError: レスポンスが空
        json.JSONDecodeError: レスポンスのJSONパース失敗
        pydantic.ValidationError: スキーマ検証失敗
    """
    payload = {
        "model": config.model,
        "maxOutputTokens": config.max_output_tokens,
        "temperature": config.temperature,
        "input": _build_input_with_schema(prompt, schema),
        "jsonMode": True,
    }
    try:
        response = requests.post(
            config.url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=config.timeout_seconds,
        )
    except requests.Timeout as exc:
        raise RuntimeError(
            "Geminiプロキシの応答がタイムアウトしました "
            f"(model={config.model}, timeout={config.timeout_seconds:g}秒)。"
            "院内プロキシの疎通と GEMINI_MODEL の設定を確認してください。"
        ) from exc
    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Geminiプロキシへ接続できませんでした。"
            "GEMINI_PROXY_URL とコンテナからの疎通を確認してください。"
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Geminiプロキシへのリクエストに失敗しました: {exc}") from exc
    response.encoding = "utf-8"

    if response.status_code != 200:
        raise RuntimeError(
            f"Geminiプロキシがエラーを返しました "
            f"(HTTP {response.status_code}): {response.text[:500]}"
        )

    text = _strip_code_fence(response.text.strip())
    if not text:
        raise ValueError("Geminiプロキシのレスポンスが空です")

    json_data = json.loads(text)
    if isinstance(json_data, dict) and json_data.get("error") is True:
        raise RuntimeError(f"Geminiプロキシがエラーを返しました: {text[:500]}")
    return schema.model_validate(json_data)


def _build_input_with_schema(prompt: str, schema: type[BaseModel]) -> str:
    """プロンプトに出力JSON Schemaの指示を付加する."""
    schema_json = json.dumps(
        to_gemini_response_json_schema(schema.model_json_schema()),
        ensure_ascii=False,
    )
    return prompt + _SCHEMA_INSTRUCTION.format(schema_json=schema_json)


def _strip_code_fence(text: str) -> str:
    """コードフェンス（```json ... ```）で囲まれていたら中身を取り出す."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines[1:]).strip()


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"環境変数 {name} は整数で指定してください: {raw!r}") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"環境変数 {name} は数値で指定してください: {raw!r}") from exc

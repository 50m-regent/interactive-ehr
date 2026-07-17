"""Pydantic JSON Schema を Gemini が受け付けるサブセットへ変換するユーティリティ.

Vertex AI バックエンド(構造化出力の response_json_schema)と
閉域プロキシバックエンド(プロンプト埋め込み)の両方から利用される。
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

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


def to_gemini_response_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Convert Pydantic JSON Schema to the subset accepted by Gemini."""
    sanitized = _sanitize_json_schema_node(deepcopy(dict(schema)))
    _relax_recursive_layout_children(sanitized)
    return sanitized


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


def _relax_recursive_layout_children(schema: dict[str, Any]) -> None:
    """Avoid required `$ref` loops in layout widget child schemas.

    Gemini rejects required recursive references in JSON Schema. Layout children
    are still validated after generation by `schema.model_validate()`.
    """
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return

    generic_widget = {
        "type": "object",
        "additionalProperties": True,
        "description": "WidgetSpec object validated by the application after generation.",
    }

    columns = defs.get("ColumnsSpec")
    if isinstance(columns, dict):
        columns_items = (
            columns.get("properties", {})
            .get("columns", {})
            .get("items", {})
        )
        if isinstance(columns_items, dict):
            columns_items["items"] = generic_widget

    tabs = defs.get("TabsSpec")
    if isinstance(tabs, dict):
        tab_items = tabs.get("properties", {}).get("tabs", {}).get("items", {})
        if isinstance(tab_items, dict):
            tab_items["items"] = generic_widget

    expander = defs.get("ExpanderSpec")
    if isinstance(expander, dict):
        children = expander.get("properties", {}).get("children", {})
        if isinstance(children, dict):
            children["items"] = generic_widget

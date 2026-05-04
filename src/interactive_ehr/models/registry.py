"""Helpers for discovering DWH models and generating fake context data."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast, get_args, get_origin

import pandas as pd

from interactive_ehr import models
from interactive_ehr.models import DwhBaseModel


DEFAULT_FAKE_ROWS = 5


@dataclass(frozen=True)
class DwhFieldInfo:
    """Small prompt-facing description of one DWH model field."""

    name: str
    type_name: str
    description: str | None = None


@dataclass(frozen=True)
class DwhModelInfo:
    """Small prompt-facing description of one DWH model."""

    name: str
    description: str
    fields: list[DwhFieldInfo]


def list_dwh_model_names() -> list[str]:
    """Return all concrete DWH model names exported by ``interactive_ehr.models``."""

    return [
        name
        for name in models.__all__
        if name != "DwhBaseModel" and _is_dwh_model(getattr(models, name, None))
    ]


def get_dwh_model(model_name: str) -> type[DwhBaseModel]:
    """Return the concrete DWH model class for ``model_name``."""

    model = getattr(models, model_name, None)
    if not _is_dwh_model(model):
        raise KeyError(f"未定義のDWHモデルです: {model_name}")
    return cast(type[DwhBaseModel], model)


def has_dwh_model(model_name: str) -> bool:
    """Return whether ``model_name`` resolves to a concrete DWH model."""

    return _is_dwh_model(getattr(models, model_name, None))


def get_dwh_model_info(model_name: str) -> DwhModelInfo:
    """Return prompt metadata for one DWH model."""

    model = get_dwh_model(model_name)
    return DwhModelInfo(
        name=model_name,
        description=(model.__doc__ or "").strip(),
        fields=[
            DwhFieldInfo(
                name=_field_display_name(field_name, field_info),
                type_name=_type_name(field_info.annotation),
                description=field_info.description,
            )
            for field_name, field_info in model.model_fields.items()
        ],
    )


def iter_dwh_model_info(
    *,
    model_names: Iterable[str] | None = None,
) -> list[DwhModelInfo]:
    """Return prompt metadata for all or selected DWH models."""

    names = list(model_names) if model_names is not None else list_dwh_model_names()
    return [get_dwh_model_info(name) for name in names]


def dwh_context_key(model_name: str) -> str:
    """Return the stable context key for a DWH model."""

    return f"dwh_{model_name}"


def dwh_field_names(model_name: str) -> list[str]:
    """Return display field names for ``model_name``."""

    return [field.name for field in get_dwh_model_info(model_name).fields]


def fake_dwh_dataframe(model_name: str, *, n: int = DEFAULT_FAKE_ROWS) -> pd.DataFrame:
    """Generate fake rows for ``model_name`` as a DataFrame with DWH column names."""

    model = get_dwh_model(model_name)
    rows = model.fake(n=n)
    if isinstance(rows, DwhBaseModel):
        rows = [rows]
    return pd.DataFrame([row.model_dump(mode="python", by_alias=True) for row in rows])


def build_dwh_context_for_model_names(
    model_names: Iterable[str],
    *,
    n: int = DEFAULT_FAKE_ROWS,
) -> dict[str, object]:
    """Build Streamlit context entries for DWH models."""

    return {
        dwh_context_key(model_name): fake_dwh_dataframe(model_name, n=n)
        for model_name in dict.fromkeys(model_names)
    }


def _is_dwh_model(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, DwhBaseModel) and value is not DwhBaseModel


def _field_display_name(field_name: str, field_info: Any) -> str:
    alias = getattr(field_info, "alias", None)
    return str(alias or field_name)


def _type_name(annotation: object) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation))
    args = ", ".join(_type_name(arg) for arg in get_args(annotation))
    origin_name = getattr(origin, "__name__", str(origin))
    return f"{origin_name}[{args}]"

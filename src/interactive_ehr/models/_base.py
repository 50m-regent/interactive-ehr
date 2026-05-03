"""DWHモデル共通ベースクラス."""

from __future__ import annotations

import random
import string
from datetime import date, time
from decimal import Decimal
from typing import Literal, Self, get_args, get_origin, overload

from pydantic import BaseModel, ConfigDict


def _is_optional(annotation: type) -> tuple[bool, type]:
    """Optional[X] (= X | None) かどうかを判定し、内側の型を返す."""
    origin = get_origin(annotation)
    if origin is not type(int | str):  # types.UnionType
        return False, annotation
    args = get_args(annotation)
    none_types = {type(None)}
    non_none = [a for a in args if a not in none_types]
    if len(non_none) == 1 and type(None) in args:
        return True, non_none[0]
    return False, annotation


def _fake_value(tp: type) -> str | int | float | Decimal | date | time:
    """型に応じたランダムなダミー値を生成する."""
    if tp is str:
        return "DUMMY_" + "".join(random.choices(string.ascii_uppercase, k=4))
    if tp is int:
        return random.randint(0, 999)
    if tp is float:
        return round(random.uniform(0.0, 999.0), 2)
    if tp is Decimal:
        return Decimal(str(round(random.uniform(0.0, 999.0), 2)))
    if tp is date:
        return date(
            random.randint(2020, 2025),
            random.randint(1, 12),
            random.randint(1, 28),
        )
    if tp is time:
        return time(random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
    # フォールバック: 空文字列
    return ""


class DwhBaseModel(BaseModel):
    """全DWHテーブルモデルの基底クラス.

    frozen=True で不変性を保証。
    populate_by_name=True でalias・フィールド名どちらでもデータ投入可能。
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    @classmethod
    @overload
    def fake(cls, n: Literal[1] = 1, **overrides: object) -> Self: ...

    @classmethod
    @overload
    def fake(cls, n: int, **overrides: object) -> list[Self]: ...

    @classmethod
    def fake(cls, n: int = 1, **overrides: object) -> Self | list[Self]:
        """ランダムなダミーデータを生成する.

        Args:
            n: 生成するインスタンス数。1の場合は単体を返す。
            **overrides: 固定したいフィールド値。指定されたフィールドは
                         ランダム生成せず、与えられた値をそのまま使う。

        Returns:
            n=1 のときは DwhBaseModel インスタンス1つ、
            n>1 のときは list[DwhBaseModel]。
        """

        def _build_one() -> Self:
            data: dict[str, object] = {}
            for field_name, field_info in cls.model_fields.items():
                if field_name in overrides:
                    data[field_name] = overrides[field_name]
                    continue

                annotation = field_info.annotation
                is_opt, inner_tp = _is_optional(annotation)

                if is_opt:
                    # Optional フィールドは 50% の確率で None
                    if random.random() < 0.5:
                        data[field_name] = None
                        continue

                data[field_name] = _fake_value(inner_tp)
            return cls.model_validate(data)

        if n == 1:
            return _build_one()
        return [_build_one() for _ in range(n)]

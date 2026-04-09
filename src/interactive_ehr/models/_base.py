"""DWHモデル共通ベースクラス."""

from pydantic import BaseModel, ConfigDict


class DwhBaseModel(BaseModel):
    """全DWHテーブルモデルの基底クラス.

    frozen=True で不変性を保証。
    populate_by_name=True でalias・フィールド名どちらでもデータ投入可能。
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

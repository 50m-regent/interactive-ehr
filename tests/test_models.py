"""DWHモデルのテスト."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from interactive_ehr.models import DwhBaseModel
from interactive_ehr.models.registry import (
    build_dwh_context_for_model_names,
    dwh_context_key,
    dwh_field_names,
    get_dwh_model_info,
    list_dwh_model_names,
    load_dwh_dataframe,
)
from interactive_ehr.models.patient import 患者基本, 患者プロフィール, 身体測定情報
from interactive_ehr.models.order_exam import 検体検査, 検体検査結果
from interactive_ehr.models.order_treatment import 処方, 手術実施
from interactive_ehr.models.order_record import 病名, サマリ管理
from interactive_ehr.models.mr import カルテ記事DR
from interactive_ehr.models.nurse import バイタル, 看護DB_ヘルスプロモーション


class TestDwhBaseModel:
    """ベースモデルのテスト."""

    def test_frozen(self) -> None:
        p = 患者基本()
        with pytest.raises(ValidationError):
            p.性別 = "男"  # type: ignore[misc]

    def test_all_models_inherit_base(self) -> None:
        from interactive_ehr import models

        for name in models.__all__:
            cls = getattr(models, name)
            assert issubclass(cls, DwhBaseModel)


class TestPatientModels:
    """PATIENTグループのテスト."""

    def test_patient_basic_defaults(self) -> None:
        p = 患者基本()
        assert p.匿名ID == ""
        assert p.性別 == ""
        assert p.生年月日 == date(1000, 1, 1)
        assert p.ETL更新時刻 == time(0, 0, 0)
        assert p.現在年齢 is None
        assert p.キャンセル日 is None

    def test_patient_basic_with_values(self) -> None:
        p = 患者基本(
            匿名ID="A001",
            性別="男",
            生年月日=date(1990, 5, 15),
            現在年齢=35,
        )
        assert p.匿名ID == "A001"
        assert p.性別 == "男"
        assert p.生年月日 == date(1990, 5, 15)
        assert p.現在年齢 == 35

    def test_patient_profile_instantiation(self) -> None:
        p = 患者プロフィール()
        assert p.匿名ID == ""
        assert p.患者番号 == 0.0

    def test_body_measurement_nullable(self) -> None:
        m = 身体測定情報()
        assert m.匿名ID == ""


class TestOrderModels:
    """ORDERグループのテスト."""

    def test_lab_test(self) -> None:
        t = 検体検査()
        assert t.匿名ID == ""

    def test_lab_result(self) -> None:
        r = 検体検査結果()
        assert r.匿名ID == ""

    def test_prescription(self) -> None:
        p = 処方()
        assert p.匿名ID == ""

    def test_surgery(self) -> None:
        s = 手術実施()
        assert s.匿名ID == ""

    def test_diagnosis(self) -> None:
        d = 病名()
        assert d.匿名ID == ""

    def test_summary(self) -> None:
        s = サマリ管理()
        assert s.匿名ID == ""


class TestMrModels:
    """MRグループのテスト."""

    def test_dr_record(self) -> None:
        r = カルテ記事DR()
        assert r.匿名ID == ""


class TestNurseModels:
    """NURSEグループのテスト."""

    def test_vital(self) -> None:
        v = バイタル()
        assert v.匿名ID == ""

    def test_nursing_db_with_duplicate_columns(self) -> None:
        """重複カラム名を持つモデルのテスト."""
        h = 看護DB_ヘルスプロモーション()
        assert h.飲酒回数_1 is None
        assert h.飲酒回数_2 is None

    def test_populate_by_alias(self) -> None:
        """aliasでのデータ投入テスト."""
        h = 看護DB_ヘルスプロモーション.model_validate({"飲酒回数": 3})
        assert h.飲酒回数_1 == 3


class TestModelCount:
    """生成されたモデル数のテスト."""

    def test_total_model_count(self) -> None:
        from interactive_ehr import models

        model_classes = [
            name
            for name in models.__all__
            if name != "DwhBaseModel"
        ]
        # 136テーブル分のモデルが生成されていること
        assert len(model_classes) >= 130


class TestDwhRegistry:
    """DWHモデルレジストリのテスト."""

    def test_lists_concrete_models_without_base(self) -> None:
        model_names = list_dwh_model_names()

        assert "DwhBaseModel" not in model_names
        assert "患者基本" in model_names
        assert "検体検査結果" in model_names

    def test_model_info_uses_dwh_field_names(self) -> None:
        info = get_dwh_model_info("検体検査結果")

        field_names = [field.name for field in info.fields]
        assert info.name == "検体検査結果"
        assert "検索日(採取日)" in field_names
        assert "結果(数値)" in field_names

    def test_fake_context_uses_stable_dwh_context_key(self) -> None:
        context = build_dwh_context_for_model_names(["患者基本"], n=5)

        dataframe = context[dwh_context_key("患者基本")]
        assert isinstance(dataframe, pd.DataFrame)
        assert list(dataframe.columns) == dwh_field_names("患者基本")
        assert len(dataframe) == 5

    def test_load_dwh_dataframe_prefers_csv(self, tmp_path: Path) -> None:
        csv_dir = tmp_path / "dwh"
        csv_dir.mkdir()
        pd.DataFrame(
            [
                {
                    "匿名ID": "CSV_001",
                    "性別": "男",
                    "生年月日": "1980-01-02",
                },
            ],
        ).to_csv(csv_dir / "患者基本.csv", index=False, encoding="utf-8-sig")

        dataframe = load_dwh_dataframe("患者基本", csv_dir=csv_dir)

        assert dataframe.loc[0, "匿名ID"] == "CSV_001"
        assert list(dataframe.columns) == ["匿名ID", "性別", "生年月日"]

    def test_load_dwh_dataframe_falls_back_to_fake(self, tmp_path: Path) -> None:
        dataframe = load_dwh_dataframe("患者基本", n=2, csv_dir=tmp_path)

        assert list(dataframe.columns) == dwh_field_names("患者基本")
        assert len(dataframe) == 2

    def test_context_builder_uses_csv_loader(self, tmp_path: Path) -> None:
        pd.DataFrame([{"匿名ID": "CSV_002"}]).to_csv(
            tmp_path / "患者基本.csv",
            index=False,
            encoding="utf-8-sig",
        )

        context = build_dwh_context_for_model_names(["患者基本"], csv_dir=tmp_path)

        dataframe = context[dwh_context_key("患者基本")]
        assert isinstance(dataframe, pd.DataFrame)
        assert dataframe.loc[0, "匿名ID"] == "CSV_002"


class TestFake:
    """fake()メソッドのテスト."""

    def test_single_instance(self) -> None:
        """n=1 (デフォルト) で単体インスタンスを返す."""
        p = 患者基本.fake()
        assert isinstance(p, 患者基本)

    def test_multiple_instances(self) -> None:
        """n>1 でリストを返す."""
        ps = 患者基本.fake(n=5)
        assert isinstance(ps, list)
        assert len(ps) == 5
        assert all(isinstance(p, 患者基本) for p in ps)

    def test_overrides(self) -> None:
        """overrides で指定した値が反映される."""
        p = 患者基本.fake(匿名ID="TEST_001", 性別="男")
        assert p.匿名ID == "TEST_001"
        assert p.性別 == "男"

    def test_str_fields_populated(self) -> None:
        """str型フィールドにダミー文字列が入る."""
        p = 患者基本.fake()
        assert isinstance(p.匿名ID, str)
        assert len(p.匿名ID) > 0

    def test_date_fields_populated(self) -> None:
        """date型フィールドに有効な日付が入る."""
        p = 患者基本.fake()
        assert isinstance(p.生年月日, date)
        assert p.生年月日.year >= 2020

    def test_optional_fields_type(self) -> None:
        """Optional型フィールドは None か正しい型."""
        p = 患者基本.fake()
        assert p.現在年齢 is None or isinstance(p.現在年齢, int)
        assert p.キャンセル日 is None or isinstance(p.キャンセル日, date)

    def test_all_models_can_fake(self) -> None:
        """全モデルで fake() がエラーなく実行できる."""
        from interactive_ehr import models

        for name in models.__all__:
            if name == "DwhBaseModel":
                continue
            cls = getattr(models, name)
            instance = cls.fake()
            assert isinstance(instance, cls), f"{name}.fake() failed"

    def test_frozen_after_fake(self) -> None:
        """fake() で生成したインスタンスも frozen のまま."""
        p = 患者基本.fake()
        with pytest.raises(ValidationError):
            p.性別 = "女"  # type: ignore[misc]

"""DWHモデルのテスト."""

from __future__ import annotations

from datetime import date, time

import pytest
from pydantic import ValidationError

from interactive_ehr.models import DwhBaseModel
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

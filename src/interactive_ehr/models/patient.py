"""自動生成されたDWHテーブルモデル."""

from __future__ import annotations

from datetime import date, time
from pydantic import Field

from interactive_ehr.models._base import DwhBaseModel


class 患者基本(DwhBaseModel):
    """最新の患者基本情報（1患者につき1レコード）."""

    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    件数: int = 1
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    名寄先患者ID: str = ""
    名寄先匿名ID: str = ""
    患者氏名: str = ""
    患者カナ姓: str = ""
    患者カナ名: str = ""
    患者カナ氏名: str = ""
    アクティブ対象: str = ""
    現在年齢: int | None = None
    現在月齢: int | None = None
    現在日齢: int | None = None
    性別: str = ""
    キャンセル日の定義: str = ""
    キャンセル日: date | None = None
    キャンセル時刻: time | None = None
    入力日の定義: str = ""
    更新者ID: str = ""
    更新者: str = ""
    更新者職種: str = ""
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    生年月日: date = date(1000, 1, 1)
    患者状態: str = ""
    国籍: str = ""
    県名: str = ""
    住所コード: str = ""
    郵便番号: str = ""
    初来院日: date | None = None
    入院回数: int = 0
    血液型ABO式: str = ""
    血液型ABO亜型式: str = ""
    血液型RH式: str = ""
    血液型コメント: str = ""


class 患者プロフィール(DwhBaseModel):
    """最新の患者プロフィール（1患者につき1レコード）."""

    ETL更新日: date = date(1000, 1, 1)
    件数: int = 1
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    キャンセル日の定義: str = ""
    キャンセル日: date | None = None
    キャンセル時刻: time | None = None
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    入力者ID: str = ""
    入力者: str = ""
    入力者職種: str = ""
    更新者ID: str = ""
    更新者: str = ""
    更新者職種: str = ""
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    新生児: str = ""
    配偶者の有無: str = ""
    結婚年月: str = ""
    子供人数: int | None = None
    職業: str = ""
    造影剤アレルギーの有無: str = ""
    食物アレルギーの有無: str = ""
    薬物アレルギーの有無: str = ""
    その他アレルギー1の定義: str = ""
    その他アレルギー1の有無: str = ""
    その他アレルギー2の定義: str = ""
    その他アレルギー2の有無: str = ""
    その他アレルギー3の定義: str = ""
    その他アレルギー3の有無: str = ""
    その他のアレルギー: str = ""
    アレルギーコメント: str = ""
    四肢障害の有無: str = ""
    視覚障害の有無: str = ""
    聴覚障害の有無: str = ""
    言語障害の有無: str = ""
    精神障害の有無: str = ""
    排泄障害の有無: str = ""
    意識障害の有無: str = ""
    その他障害1の定義: str = ""
    その他障害1の有無: str = ""
    その他障害2の定義: str = ""
    その他障害2の有無: str = ""
    その他障害3の定義: str = ""
    その他障害3の有無: str = ""
    その他の障害: str = ""
    障害コメント: str = ""
    看護度: str = ""
    看護必要度: str = ""
    救護区分: str = ""
    安静度: str = ""
    重症度: str = ""
    身長: float | None = None
    体重: float | None = None
    体重測定日: date | None = None
    体表面積: float | None = None
    頭囲: float | None = None
    胸囲: float | None = None
    腹囲: float | None = None
    矯正視力_右_: float | None = Field(None, alias="矯正視力(右)")
    矯正視力_左_: float | None = Field(None, alias="矯正視力(左)")
    裸眼視力_右_: float | None = Field(None, alias="裸眼視力(右)")
    裸眼視力_左_: float | None = Field(None, alias="裸眼視力(左)")
    矯正近視力_右_: float | None = Field(None, alias="矯正近視力(右)")
    矯正近視力_左_: float | None = Field(None, alias="矯正近視力(左)")
    眼圧_右_: float | None = Field(None, alias="眼圧(右)")
    眼圧_左_: float | None = Field(None, alias="眼圧(左)")
    聴力_右_: int | None = Field(None, alias="聴力(右)")
    聴力_左_: int | None = Field(None, alias="聴力(左)")
    握力_右_: float | None = Field(None, alias="握力(右)")
    握力_左_: float | None = Field(None, alias="握力(左)")
    筋力_右下肢_: float | None = Field(None, alias="筋力(右下肢)")
    筋力_左下肢_: float | None = Field(None, alias="筋力(左下肢)")
    身体機能計測日: date | None = None
    身体装具: str = ""
    肝機能障害の有無: str = ""
    腎機能障害の有無: str = ""
    気管支喘息の有無: str = ""
    肺疾患の有無: str = ""
    心疾患の有無: str = ""
    高血圧の有無: str = ""
    糖尿病の有無: str = ""
    出血傾向の有無: str = ""
    前立腺肥大の有無: str = ""
    緑内障の有無: str = ""
    血液疾患の有無: str = ""
    甲状腺疾患の有無: str = ""
    呼吸器不全の有無: str = ""
    心電図異常の有無: str = ""
    抗凝固血小板療法の有無: str = ""
    閉所恐怖症の有無: str = ""
    心筋梗塞の有無: str = ""
    狭心症の有無: str = ""
    性病の有無: str = ""
    ツベルクリン反応の有無: str = ""
    遺伝性疾患_家族_の有無: str = Field("", alias="遺伝性疾患(家族)の有無")
    成人病負荷_家族_の有無: str = Field("", alias="成人病負荷(家族)の有無")
    精神神経疾患の有無: str = ""
    遺伝子型: str = ""
    入院の有無: str = ""
    手術の有無: str = ""
    輸血の有無: str = ""
    MRSA_____: str = Field("", alias="MRSA(+,-)")
    B型肝炎_____: str = Field("", alias="B型肝炎(+,-)")
    C型肝炎_____: str = Field("", alias="C型肝炎(+,-)")
    HIV_____: str = Field("", alias="HIV(+,-)")
    緑膿菌_____: str = Field("", alias="緑膿菌(+,-)")
    TB_____: str = Field("", alias="TB(+,-)")
    TPHA_____: str = Field("", alias="TPHA(+,-)")
    VRE_____: str = Field("", alias="VRE(+,-)")
    クラミジアIgG_____: str = Field("", alias="クラミジアIgG(+,-)")
    クラミジアIgA_____: str = Field("", alias="クラミジアIgA(+,-)")
    その他感染症1の定義: str = ""
    その他感染症1の有無: str = ""
    その他感染症2の定義: str = ""
    その他感染症2の有無: str = ""
    その他感染症3の定義: str = ""
    その他感染症3の有無: str = ""
    感染症フリーコメント: str = ""
    感染経路: str = ""
    体温: float | None = None
    脈拍: int | None = None
    不整脈の有無: str = ""
    呼吸数: int | None = None
    血圧_最高_: int | None = Field(None, alias="血圧(最高)")
    血圧_最低_: int | None = Field(None, alias="血圧(最低)")
    中心静脈圧: int | None = None
    バイタル測定日: date | None = None
    ペースメーカーの有無: str = ""
    ペースメーカータイプ: str = ""
    ペースメーカー装着日: date | None = None
    外科用クリップの有無: str = ""
    脳動脈クリップの有無: str = ""
    人工関節の有無: str = ""
    人工弁の有無: str = ""
    骨折接合材の有無: str = ""
    義歯の有無: str = ""
    金属染色_刺青_の有無: str = Field("", alias="金属染色(刺青)の有無")
    眼内レンズの有無: str = ""
    その他の体内金属: str = ""
    インプラント装着日: date | None = None
    総ビリルビン: float | None = None
    血清クレアチニン: float | None = None
    クレアチニンクリアランス: float | None = None
    その他検査結果値1: float | None = None
    その他検査結果値2: float | None = None
    その他検査結果値3: float | None = None
    インスリン使用の有無: str = ""
    降圧利尿剤使用の有無: str = ""
    抗凝固剤使用の有無: str = ""
    抗痙攣剤使用の有無: str = ""
    抗生物質使用の有無: str = ""
    ジギタリス使用の有無: str = ""
    ステロイド使用の有無: str = ""
    抗コリン剤筋注使用の有無: str = ""
    向精神薬使用の有無: str = ""
    常用薬1コード: str = ""
    常用薬1: str = ""
    常用薬2コード: str = ""
    常用薬2: str = ""
    常用薬3コード: str = ""
    常用薬3: str = ""
    常用薬4コード: str = ""
    常用薬4: str = ""
    常用薬5コード: str = ""
    常用薬5: str = ""
    常用薬6コード: str | None = None
    常用薬6: str | None = None
    常用薬7コード: str | None = None
    常用薬7: str | None = None
    常用薬8コード: str | None = None
    常用薬8: str | None = None
    常用薬9コード: str | None = None
    常用薬9: str | None = None
    常用薬10コード: str | None = None
    常用薬10: str | None = None
    常用薬11コード: str | None = None
    常用薬11: str | None = None
    常用薬12コード: str | None = None
    常用薬12: str | None = None
    常用薬13コード: str | None = None
    常用薬13: str | None = None
    常用薬14コード: str | None = None
    常用薬14: str | None = None
    常用薬15コード: str | None = None
    常用薬15: str | None = None
    常用薬16コード: str | None = None
    常用薬16: str | None = None
    常用薬17コード: str | None = None
    常用薬17: str | None = None
    常用薬18コード: str | None = None
    常用薬18: str | None = None
    常用薬19コード: str | None = None
    常用薬19: str | None = None
    常用薬20コード: str | None = None
    常用薬20: str | None = None
    常用薬21コード: str | None = None
    常用薬21: str | None = None
    常用薬22コード: str | None = None
    常用薬22: str | None = None
    常用薬23コード: str | None = None
    常用薬23: str | None = None
    常用薬24コード: str | None = None
    常用薬24: str | None = None
    常用薬25コード: str | None = None
    常用薬25: str | None = None
    常用薬26コード: str | None = None
    常用薬26: str | None = None
    常用薬27コード: str | None = None
    常用薬27: str | None = None
    常用薬28コード: str | None = None
    常用薬28: str | None = None
    常用薬29コード: str | None = None
    常用薬29: str | None = None
    常用薬30コード: str | None = None
    常用薬30: str | None = None
    常用薬コメント: str = ""
    喫煙: str = ""
    喫煙本数: int | None = None
    喫煙開始年齢: int | None = None
    喫煙中止年齢: int | None = None
    飲酒: str = ""
    便通: int | None = None
    便通頻度: int | None = None
    妊娠経験の有無: str = ""
    妊娠中: str = ""
    出産回数: int | None = None
    信仰の有無: str = ""
    VIP対象: str = ""
    要注意対象: str = ""
    尊厳死希望の有無: str = ""
    臓器提供希望の有無: str = ""
    癌告知希望の有無: str = ""
    その他情報1の定義: str = ""
    その他情報1の有無: str = ""
    その他情報2の定義: str = ""
    その他情報2の有無: str = ""
    その他情報3の定義: str = ""
    その他情報3の有無: str = ""
    英語対応必要患者: str | None = None
    治験の有無: str | None = None
    探索の有無: str | None = None
    透析の有無: str | None = None
    高度の有無: str | None = None
    その他の有無: str | None = None
    病理同意書有無: str | None = None
    病理同意日付__: date | None = Field(None, alias="病理同意日付  ")
    MRI造影剤アレルギー: str | None = None
    造影剤アレルギーの症状: str | None = None
    アレルギー性鼻炎: str | None = None
    人口内耳: str | None = None
    インプラント: str | None = None
    髄内釘: str | None = None
    避妊具: str | None = None
    ペッツ: str | None = None
    金属プレート: str | None = None
    金属プレートの部位: str | None = None
    骨折接合材の種類: str | None = None
    蕁麻疹: str | None = None
    異型輸血: str | None = None
    緊急連絡先携帯番号1: str | None = None
    緊急連絡先携帯番号2: str | None = None
    キーパーソン携帯番号: str | None = None
    保護義務者携帯番号: str | None = None
    退院後連絡先携帯番号: str | None = None
    自助具: str | None = None
    自助具コメント: str | None = None
    利き手: str | None = None
    利き手制限: str | None = None
    ケアマネージャー_所属: str | None = Field(None, alias="ケアマネージャー・所属")
    ケアマネージャー_氏名: str | None = Field(None, alias="ケアマネージャー・氏名")
    ケアマネージャー_TEL: str | None = Field(None, alias="ケアマネージャー・TEL")
    介護保険: str | None = None
    判定区分: str | None = None
    身体障害者手帳: str | None = None
    等級: str | None = None
    聴覚_平衡機能障害_1: str | None = Field(None, alias="聴覚/平衡機能障害")
    音声_言語_咀嚼: str | None = Field(None, alias="音声/言語/咀嚼")
    肢体不自由_1: str | None = Field(None, alias="肢体不自由")
    心臓機能障害_1: str | None = Field(None, alias="心臓機能障害")
    膀胱_直腸機能障害_1: str | None = Field(None, alias="膀胱/直腸機能障害")
    ヒト免疫不全ウィルスによる免疫機能障害: str | None = None
    腎臓機能障害: str | None = None
    呼吸器機能障害_1: str | None = Field(None, alias="呼吸器機能障害")
    小腸機能障害_1: str | None = Field(None, alias="小腸機能障害")
    精神障害者保険福祉手帳_1: str | None = Field(None, alias="精神障害者保険福祉手帳")
    生活保護: str | None = None
    その他コメント: str | None = None
    活用しているサービス: str | None = None
    窓口_担当者: str | None = Field(None, alias="窓口・担当者")
    連絡先: str | None = None
    在宅療養上での家族の負担: str | None = None
    在宅療養上での家族の負担コメント: str | None = None
    小児慢性特定疾患: str | None = None
    特定疾患_1: str | None = Field(None, alias="特定疾患")
    緊急連絡先1関係フリー: str | None = None
    緊急連絡先2関係フリー: str | None = None
    キーパーソン連絡先関係フリー: str | None = None
    人工内耳: str = ""
    人工内耳_機種: str = Field("", alias="人工内耳 機種")
    人工内耳_設置日: date | None = Field(None, alias="人工内耳 設置日")
    体内インプラント_電子デバイス: str = Field(
        "", alias="体内インプラント・電子デバイス"
    )
    体内インプラント_電子デバイス_フリー: str = Field(
        "", alias="体内インプラント・電子デバイス フリー"
    )
    造影剤アレルギ_MR_: str = Field("", alias="造影剤アレルギ(MR)")
    造影剤アレルギ_MR__コメント: str = Field("", alias="造影剤アレルギ(MR) コメント")
    造影剤アレルギ_CT__コメント: str = Field("", alias="造影剤アレルギ(CT) コメント")
    ビグアナイド系処方: str = ""
    ビグアナイド系処方_コメント: str = Field("", alias="ビグアナイド系処方 コメント")
    βブロッカー服用: str = ""
    βブロッカー服用_コメント: str = Field("", alias="βブロッカー服用 コメント")
    パワーボート: str = ""
    腎機能コメント: str = ""
    認知症: str = ""
    放射線被ばく: str = ""
    障害に関するコメント: str = ""
    その他安全情報: str = ""
    ABO不適合移植患者: str = ""
    脳動脈クリップー機種等: str = ""
    ICD_CRTD機種等: str = Field("", alias="ICD・CRTD機種等")
    ICD_CRTD設置日: date | None = Field(None, alias="ICD・CRTD設置日")
    判定済み: str = ""
    要支援: str = ""
    要介護: str = ""
    認定調査済み: str = ""
    申請書提出済み: str = ""
    未申請: str = ""
    担当ケアマネージャー氏名: str = ""
    担当ケアマネージャー連絡先: str = ""
    担当ケアマネージャーその他情報: str = ""
    デイサービス: str = ""
    デイサービス_フリーテキスト_: str = Field("", alias="デイサービス(フリーテキスト)")
    ショートステイ: str = ""
    ショートステイ_フリーテキスト_: str = Field(
        "", alias="ショートステイ(フリーテキスト)"
    )
    訪問看護_往診_: str = Field("", alias="訪問看護(往診)")
    訪問看護_往診__フリーテキスト_: str = Field(
        "", alias="訪問看護(往診)(フリーテキスト)"
    )
    訪問看護: str = ""
    訪問看護_フリーテキスト_: str = Field("", alias="訪問看護(フリーテキスト)")
    訪問リハビリ: str = ""
    訪問リハビリ_フリーテキスト_: str = Field("", alias="訪問リハビリ(フリーテキスト)")
    ヘルパー: str = ""
    ヘルパー_フリーテキスト_: str = Field("", alias="ヘルパー(フリーテキスト)")
    福祉用具レンタル: str = ""
    福祉用具レンタル_フリーテキスト_: str = Field(
        "", alias="福祉用具レンタル(フリーテキスト)"
    )
    その他_1: str = Field("", alias="その他")
    その他_フリーテキスト__1: str = Field("", alias="その他(フリーテキスト)")
    詳細情報: str = ""
    視覚障害: str = ""
    視覚障害_フリーテキスト_: str = Field("", alias="視覚障害(フリーテキスト)")
    聴覚_平衡機能障害_2: str = Field("", alias="聴覚/平衡機能障害")
    聴覚_平衡機能障害_フリーテキスト_: str = Field(
        "", alias="聴覚/平衡機能障害(フリーテキスト)"
    )
    音声機能_言語機能_咀嚼機能障害: str = Field(
        "", alias="音声機能・言語機能/咀嚼機能障害"
    )
    音声機能_言語機能_咀嚼機能障害_フリーテキスト_: str = Field(
        "", alias="音声機能・言語機能/咀嚼機能障害(フリーテキスト)"
    )
    肢体不自由_2: str = Field("", alias="肢体不自由")
    肢体不自由_フリーテキスト_: str = Field("", alias="肢体不自由(フリーテキスト)")
    腎機能障害: str = ""
    腎機能障害_フリーテキスト_: str = Field("", alias="腎機能障害(フリーテキスト)")
    心臓機能障害_2: str = Field("", alias="心臓機能障害")
    心臓機能障害_フリーテキスト_: str = Field("", alias="心臓機能障害(フリーテキスト)")
    呼吸器機能障害_2: str = Field("", alias="呼吸器機能障害")
    呼吸器機能障害_フリーテキスト_: str = Field(
        "", alias="呼吸器機能障害(フリーテキスト)"
    )
    膀胱_直腸機能障害_2: str = Field("", alias="膀胱/直腸機能障害")
    膀胱_直腸機能障害_フリーテキスト_: str = Field(
        "", alias="膀胱/直腸機能障害(フリーテキスト)"
    )
    小腸機能障害_2: str = Field("", alias="小腸機能障害")
    小腸機能障害_フリーテキスト_: str = Field("", alias="小腸機能障害(フリーテキスト)")
    ヒト免疫不全ウイルスによる免疫機能障害: str = ""
    ヒト免疫不全ウイルスによる免疫機能障害_フリーテキスト_: str = Field(
        "", alias="ヒト免疫不全ウイルスによる免疫機能障害(フリーテキスト)"
    )
    精神障害: str = ""
    精神障害_フリーテキスト_: str = Field("", alias="精神障害(フリーテキスト)")
    療育手帳: str = ""
    精神障害者保険福祉手帳_2: str = Field("", alias="精神障害者保険福祉手帳")
    特定疾患_2: str = Field("", alias="特定疾患")
    特定疾患_フリーテキスト_: str = Field("", alias="特定疾患(フリーテキスト)")
    児_小児特定疾患: str = Field("", alias="(児)小児特定疾患")
    児_小児特定疾患_フリーテキスト_: str = Field(
        "", alias="(児)小児特定疾患(フリーテキスト)"
    )
    児_育成医療: str = Field("", alias="(児)育成医療")
    児_育成医療_フリーテキスト_: str = Field("", alias="(児)育成医療(フリーテキスト)")
    児_未熟児養育医療: str = Field("", alias="(児)未熟児養育医療")
    児_未熟児養育医療_フリーテキスト_: str = Field(
        "", alias="(児)未熟児養育医療(フリーテキスト)"
    )
    生活保護受給者: str = ""
    生活保護受給者_フリーテキスト_: str = Field(
        "", alias="生活保護受給者(フリーテキスト)"
    )
    右上肢_処置禁止: str = Field("", alias="右上肢 処置禁止")
    右上肢_処置禁止_フリーテキスト_: str = Field(
        "", alias="右上肢 処置禁止(フリーテキスト)"
    )
    左上肢_処置禁止: str = Field("", alias="左上肢 処置禁止")
    左上肢_処置禁止_フリーテキスト_: str = Field(
        "", alias="左上肢 処置禁止(フリーテキスト)"
    )
    その他_2: str = Field("", alias="その他")
    その他_フリーテキスト__2: str = Field("", alias="その他(フリーテキスト)")
    CT非対応: str = ""
    リード有無: str = ""
    リードコメント: str = ""
    リード設置日: date | None = None
    パワーボート埋込日: date | None = None
    体内インプラント_電子デバイス_フリー2: str = Field(
        "", alias="体内インプラント・電子デバイス フリー2"
    )
    体内インプラント_電子デバイス_フリー3: str = Field(
        "", alias="体内インプラント・電子デバイス フリー3"
    )
    体内インプラント_電子デバイス_フリー4: str = Field(
        "", alias="体内インプラント・電子デバイス フリー4"
    )
    体内インプラント_電子デバイス_フリー5: str = Field(
        "", alias="体内インプラント・電子デバイス フリー5"
    )
    体内インプラント_電子デバイス_フリー6: str = Field(
        "", alias="体内インプラント・電子デバイス フリー6"
    )
    体内インプラント_電子デバイス_フリー7: str = Field(
        "", alias="体内インプラント・電子デバイス フリー7"
    )
    体内インプラント_電子デバイス_フリー8: str = Field(
        "", alias="体内インプラント・電子デバイス フリー8"
    )
    体内インプラント_電子デバイス_フリー9: str = Field(
        "", alias="体内インプラント・電子デバイス フリー9"
    )
    体内インプラント_電子デバイス_フリー10: str = Field(
        "", alias="体内インプラント・電子デバイス フリー10"
    )
    体内インプラント_電子デバイス_フリー11: str = Field(
        "", alias="体内インプラント・電子デバイス フリー11"
    )
    体内インプラント_電子デバイス_フリー12: str = Field(
        "", alias="体内インプラント・電子デバイス フリー12"
    )
    体内インプラント_電子デバイス_フリー13: str = Field(
        "", alias="体内インプラント・電子デバイス フリー13"
    )
    体内インプラント_電子デバイス_フリー14: str = Field(
        "", alias="体内インプラント・電子デバイス フリー14"
    )
    体内インプラント_電子デバイス_フリー15: str = Field(
        "", alias="体内インプラント・電子デバイス フリー15"
    )
    体内インプラント_電子デバイス_フリー16: str = Field(
        "", alias="体内インプラント・電子デバイス フリー16"
    )
    体内インプラント_電子デバイス_フリー17: str = Field(
        "", alias="体内インプラント・電子デバイス フリー17"
    )
    体内インプラント_電子デバイス_フリー18: str = Field(
        "", alias="体内インプラント・電子デバイス フリー18"
    )
    体内インプラント_電子デバイス_フリー19: str = Field(
        "", alias="体内インプラント・電子デバイス フリー19"
    )
    体内インプラント_電子デバイス_フリー20: str = Field(
        "", alias="体内インプラント・電子デバイス フリー20"
    )
    その他の情報: str = ""
    死亡の有無: str = ""
    死亡日: date | None = None


class 身体測定情報(DwhBaseModel):
    """身体測定情報（1患者1測定につき1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    測定時年齢: int | None = None
    測定時月齢: int | None = None
    測定時日齢: int | None = None
    検索日の定義: str = ""
    検索日_測定日_: date = Field(date(1000, 1, 1), alias="検索日(測定日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    測定連番: int = 0
    測定日: date = date(1000, 1, 1)
    測定者ID: str = ""
    測定者名: str = ""
    身長: float | None = None
    体重: float | None = None
    体表面積: float | None = None
    頭囲: float | None = None
    胸囲: float | None = None
    腹囲: float | None = None


class 患者アレルギー情報(DwhBaseModel):
    """患者アレルギー情報（1患者1アレルギーにつき1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    診断時年齢: int | None = None
    診断時月齢: int | None = None
    診断時日齢: int | None = None
    検索日の定義: str = ""
    検索日_診断日_: date = Field(date(1000, 1, 1), alias="検索日(診断日)")
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    キャンセル日の定義: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    アレルギー連番: int = 0
    アレルギー種別コード: str = ""
    アレルギー種別名: str = ""
    アレルギーコード: str = ""
    アレルギー名称: str = ""
    診断日: date | None = None
    診断診療科コード: str = ""
    診断診療科: str = ""
    診断医師ID: str = ""
    診断医師名: str = ""
    診断根拠: str = ""
    症状: str = ""
    フリーコメント: str = ""
    治癒日: date | None = None


class 患者感染症情報(DwhBaseModel):
    """患者感染症情報（1患者1感染症につき1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    診断時年齢: int | None = None
    診断時月齢: int | None = None
    診断時日齢: int | None = None
    検索日の定義: str = ""
    検索日_診断日_: date = Field(date(1000, 1, 1), alias="検索日(診断日)")
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    キャンセル日の定義: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    感染症連番: int = 0
    感染症コード: str = ""
    感染症名称: str = ""
    診断日: date | None = None
    診断診療科コード: str = ""
    診断診療科: str = ""
    診断医師ID: str = ""
    診断医師名: str = ""
    フリーコメント: str = ""


class 患者担当医師情報(DwhBaseModel):
    """患者の担当医師(主治医など)情報（担当役割、担当期間ごとに1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    担当開始時年齢: int | None = None
    担当開始時月齢: int | None = None
    担当開始時日齢: int | None = None
    検索日の定義: str = ""
    検索日_開始日_: date = Field(date(1000, 1, 1), alias="検索日(開始日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    入外区分: str = ""
    診療科コード: str = ""
    診療科: str = ""
    役割コード: str = ""
    役割名称: str = ""
    担当医師ID: str = ""
    担当開始日: date | None = None
    担当終了日: date | None = None


class 妊娠歴(DwhBaseModel):
    """妊娠歴情報（1妊娠歴1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    分娩時年齢: int | None = None
    分娩時月齢: int | None = None
    分娩時日齢: int | None = None
    検索日の定義: str = ""
    検索日_最終更新日_: date = Field(date(1000, 1, 1), alias="検索日(最終更新日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    妊娠連番: str = ""
    在胎週数: int | None = None
    出生児体重: int | None = None
    性別: str = ""
    胎児数: int | None = None
    分娩様式: str = ""
    分娩場所: str | None = None


class 問診票病歴(DwhBaseModel):
    """問診票に記載されていた来院前の病歴に関する情報（1病歴1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    検索日の定義: str = ""
    検索日_発病日_: date = Field(date(1000, 1, 1), alias="検索日(発病日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    診療科コード: str = ""
    診療科: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    病歴SEQ: int = 0
    発病年齢: int | None = None
    既往歴_病名コード_: str = Field("", alias="既往歴(病名コード)")
    既往歴_病名_: str = Field("", alias="既往歴(病名)")
    病名開始日: date | None = None
    転帰: str = ""
    治療法: str = ""
    入院の有無: str = ""
    手術の有無: str = ""
    輸血の有無: str = ""


class 予約_受診歴(DwhBaseModel):
    """診察・検査の予約・受診歴情報（1予約または1受付1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    受診時年齢: int | None = None
    受診時月齢: int | None = None
    受診時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_受診日時_: date = Field(date(1000, 1, 1), alias="検索日(受診日時)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    キャンセル日の定義: str = ""
    キャンセル日: date | None = None
    キャンセル時刻: time | None = None
    キャンセル種別: str = ""
    キャンセル理由: str = ""
    診療科コード: str = ""
    診療科: str = ""
    グループコード: str = ""
    グループ: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    サブオーナー2の定義: str = ""
    サブオーナー2ID: str = ""
    サブオーナー2: str = ""
    サブオーナー2職種: str = ""
    予実区分: str = ""
    依頼診療科コード: str = ""
    依頼診療科: str = ""
    病棟コード: str = ""
    病棟名: str = ""
    受診種別: str = ""
    外来受診区分: str = ""
    予約日: date | None = None
    予約開始時刻: time | None = None
    予約終了時刻: time | None = None
    予約グループコード: str = ""
    予約グループ名: str = ""
    予約枠コマ数: int | None = None
    予約コメント1: str = ""
    予約コメント2: str = ""
    受診日: date | None = None
    到着時刻: time | None = None
    受付時刻: time | None = None
    開始時刻: time | None = None
    終了時刻: time | None = None
    会計受付時刻: time | None = None
    会計終了時刻: time | None = None
    入金終了時刻: time | None = None
    診察前検査の有無: str = ""
    診察後検査_二度診_の有無: str = Field("", alias="診察後検査(二度診)の有無")
    併科受診の有無: str = ""
    遅刻の有無: str = ""
    初再診区分: str = ""
    来院区分: str = ""
    来院経路: str = ""
    取消時コメント: str = ""
    患者用取消コメント: str = ""
    医療従事者用取消コメント: str = ""
    オーダーキー: str = ""


class 紹介(DwhBaseModel):
    """他科・他病院からの紹介や返信記事等（1文書1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    記載時年齢: int | None = None
    記載時月齢: int | None = None
    記載時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_紹介日時_: date = Field(date(1000, 1, 1), alias="検索日(紹介日時)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    キャンセル日の定義: str = ""
    キャンセル日: date | None = None
    キャンセル時刻: time | None = None
    キャンセル種別: str = ""
    キャンセル理由: str = ""
    入外区分: str = ""
    保険分類: str = ""
    診療科コード: str = ""
    診療科: str = ""
    グループコード: str = ""
    グループ: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    紹介種別コード: str = ""
    紹介種別: str = ""
    文書名: str = ""
    紹介日: date = date(1000, 1, 1)
    紹介時刻: time | None = None
    記載日: date | None = None
    記載時刻: time | None = None
    確定日: date | None = None
    承認日: date | None = None
    紹介目的: str = ""
    記事種別コード: str = ""
    記事種別: str = ""
    記事連番: int = 0
    記事内表示連番: int | None = None
    記事データ種別コード: str = ""
    記事データ種別: str = ""
    記事: str = ""
    未整形記事の有無: str = ""
    記事_未整形_: str = Field("", alias="記事(未整形)")
    プロブレム: str = ""
    紹介元医療機関コード: str = ""
    紹介元医療機関名: str = ""
    紹介元診療科コード: str = ""
    紹介元診療科名: str = ""
    紹介元医師ID: str = ""
    紹介元医師名: str = ""
    紹介先医療機関コード: str = ""
    紹介先医療機関名: str = ""
    紹介先診療科コード: str = ""
    紹介先診療科名: str = ""
    紹介先医師ID: str = ""
    紹介先医師名: str = ""
    備考: str = ""
    返信状況: str = ""
    イメージ添付有無: str | None = None
    検査結果添付有無: str | None = None
    サマリー添付有無: str | None = None


class 入退院歴(DwhBaseModel):
    """入退院歴情報（1入院1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    入院時年齢: int | None = None
    入院時月齢: int | None = None
    入院時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_入院日_: date = Field(date(1000, 1, 1), alias="検索日(入院日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    診療科コード: str = ""
    診療科: str = ""
    入院SEQ: int = 0
    入院日: date | None = None
    入院時刻: time | None = None
    入院区分: str = ""
    入院状況: str = ""
    入院時病棟コード: str = ""
    入院時病棟: str = ""
    病室コード: str = ""
    病室: str = ""
    退院日: date | None = None
    退院時刻: time | None = None
    退院時診療科コード: str = ""
    退院時診療科: str = ""
    退院時病棟コード: str = ""
    退院時病棟: str = ""
    退院時病室コード: str = ""
    退院時病室: str = ""
    在院期間: int | None = None
    入院経路: str = ""
    入院経路コメント: str = ""
    紹介の有無: str = ""
    前医療機関: str = ""
    前診療科: str = ""
    前医: str = ""
    入院時症状: str = ""
    入院時症状コメント: str = ""
    入院時病名コード: str = ""
    入院時病名: str = ""
    入院目的: str = ""
    入院目的コメント: str = ""
    入院方法: str = ""
    入院までの治療行動コード: str = ""
    入院までの治療行動: str = ""
    入院までの治療行動コメント: str = ""
    入院中主病名コード: str = ""
    入院中主病名: str = ""
    退院経路: str = ""
    退院経路コメント: str = ""
    退院方法: str = ""
    退院後の行方: str = ""
    退院後の行方コメント: str = ""
    紹介先診療科: str = ""
    紹介先医師: str = ""
    次回受診日: date | None = None
    訪問看護コード: str = ""
    訪問看護: str = ""
    訪問看護コメント: str = ""
    退院予定日: date | None = None
    退院予定区分: str = ""
    退院時病名コード: str = ""
    退院時病名: str = ""
    転帰: str = ""
    退院理由コメント: str = ""
    死亡退院の有無: str = ""
    退院時指導の有無: str = ""
    退院時指導コメント: str = ""
    診療情報提供の有無: str = ""
    併診診療科コード: str = ""
    併診診療科: str = ""


class 入院カレンダー(DwhBaseModel):
    """入院期間中の日別の診療科、病棟情報
    (転科・転棟が発生した場合はその日の最終分)（1入退院の入院期間の日ごとに1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    入院時年齢: int | None = None
    入院時月齢: int | None = None
    入院時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_暦日_: date = Field(date(1000, 1, 1), alias="検索日(暦日)")
    検索時刻: time = time(0, 0, 0)
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    診療科コード: str = ""
    診療科: str = ""
    入院SEQ: int = 0
    入院日: date | None = None
    入院時刻: time | None = None
    暦日: date = date(1000, 1, 1)
    入院実績の有無: str = ""
    経過日数: int | None = None
    入院日当日: str = ""
    転科日当日: str = ""
    転棟日当日: str = ""
    退院日当日: str = ""
    外泊: str = ""
    病棟コード: str = ""
    病棟名: str = ""
    病室コード: str = ""
    病室: str = ""
    病床コード: str = ""
    病床: str = ""
    主治医1ID: str = ""
    主治医1名: str = ""
    主治医2ID: str = ""
    主治医2名: str = ""
    担当医1ID: str = ""
    担当医1名: str = ""
    担当医2ID: str = ""
    担当医2名: str = ""
    担当医3ID: str = ""
    担当医3名: str = ""
    担当医4ID: str = ""
    担当医4名: str = ""
    担当医5ID: str = ""
    担当医5名: str = ""
    担当看護師1ID: str = ""
    担当看護師1名: str = ""
    担当看護師2ID: str = ""
    担当看護師2名: str = ""
    担当看護師3ID: str = ""
    担当看護師3名: str = ""
    担当看護師4ID: str = ""
    担当看護師4名: str = ""
    担当看護師5ID: str = ""
    担当看護師5名: str = ""
    朝食_特食区分: str = ""
    朝食_食種コード: str = ""
    朝食_食種: str = ""
    朝食_主食: str = ""
    朝食_主食量: str = ""
    朝食_飲物1: str = ""
    朝食_飲物2: str = ""
    朝食_飲物3: str = ""
    朝間食_特食区分: str = ""
    朝間食_食種コード: str = ""
    朝間食_食種: str = ""
    朝間食_主食: str = ""
    朝間食_主食量: str = ""
    朝間食_飲物1: str = ""
    朝間食_飲物2: str = ""
    朝間食_飲物3: str = ""
    昼食_特食区分: str = ""
    昼食_食種コード: str = ""
    昼食_食種: str = ""
    昼食_主食: str = ""
    昼食_主食量: str = ""
    昼食_飲物1: str = ""
    昼食_飲物2: str = ""
    昼食_飲物3: str = ""
    昼間食_特食区分: str = ""
    昼間食_食種コード: str = ""
    昼間食_食種: str = ""
    昼間食_主食: str = ""
    昼間食_主食量: str = ""
    昼間食_飲物1: str = ""
    昼間食_飲物2: str = ""
    昼間食_飲物3: str = ""
    夕食_特食区分: str = ""
    夕食_食種コード: str = ""
    夕食_食種: str = ""
    夕食_主食: str = ""
    夕食_主食量: str = ""
    夕食_飲物1: str = ""
    夕食_飲物2: str = ""
    夕食_飲物3: str = ""
    夕間食_特食区分: str = ""
    夕間食_食種コード: str = ""
    夕間食_食種: str = ""
    夕間食_主食: str = ""
    夕間食_主食量: str = ""
    夕間食_飲物1: str = ""
    夕間食_飲物2: str = ""
    夕間食_飲物3: str = ""
    ミルク1: str = ""
    ミルク1量: int | None = None
    ミルク1回数: int | None = None
    ミルク2: str = ""
    ミルク2量: int | None = None
    ミルク2回数: int | None = None
    ミルク3: str = ""
    ミルク3量: int | None = None
    ミルク3回数: int | None = None
    ミルク4: str = ""
    ミルク4量: int | None = None
    ミルク4回数: int | None = None
    ミルク5: str = ""
    ミルク5量: int | None = None
    ミルク5回数: int | None = None


class 食事(DwhBaseModel):
    """食事オーダー情報（1オーダーにつき1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    開始時年齢: int | None = None
    開始時月齢: int | None = None
    開始時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_開始日_: date = Field(date(1000, 1, 1), alias="検索日(開始日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    入外区分: str = ""
    保険分類: str = ""
    診療科コード: str = ""
    診療科: str = ""
    病棟コード: str = ""
    病棟: str = ""
    食事場所フラグ: str | None = None
    食事場所コード: str = ""
    食事場所: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    変更理由コード: str | None = None
    変更理由: str | None = None
    食事開始日: date = date(1000, 1, 1)
    食事開始時刻: str | None = None
    食事終了日: date | None = None
    食事終了時刻: str = ""
    食種コード: str = ""
    食種: str = ""
    欠食の有無: str = ""
    食事回数: str = ""
    主食コード: str = ""
    主食: str = ""
    主食量コード: str = ""
    主食量: str = ""
    エネルギー名: str | None = None
    エネルギー量: str | None = None
    エネルギー単位表示: str | None = None
    蛋白質名: str | None = None
    蛋白質量: str | None = None
    蛋白質単位表示: str | None = None
    脂質名: str | None = None
    脂質量: str | None = None
    脂質単位表示: str | None = None
    糖質名: str | None = None
    糖質量: str | None = None
    糖質単位表示: str | None = None
    カルシウム名: str | None = None
    カルシウム量: str | None = None
    カルシウム単位表示: str | None = None
    鉄分名: str | None = None
    鉄分量: str | None = None
    鉄分単位表示: str | None = None
    水分名: str | None = None
    水分量: str | None = None
    水分単位表示: str | None = None
    カリウム名: str | None = None
    カリウム量: str | None = None
    カリウム単位表示: str | None = None
    塩分名: str | None = None
    塩分量: str | None = None
    塩分表示単位: str | None = None
    副食コード: str | None = None
    副食: str | None = None
    経管_調乳: str = Field("", alias="経管・調乳")
    経管栄養_調乳回数: int | None = Field(None, alias="経管栄養・調乳回数")
    飲み物コード: str | None = None
    飲み物: str | None = None
    選択食: str = ""
    特食の有無: str = ""
    特食理由: str = ""
    当回コメントコード1: str | None = None
    当回コメントコード2: str | None = None
    当回コメントコード3: str | None = None
    当回コメントコード4: str | None = None
    当回コメント1: str | None = None
    当回コメント2: str | None = None
    当回コメント3: str | None = None
    当回コメント4: str | None = None
    当回フリーコメント: str | None = None
    使用禁止食品コード1: str = ""
    使用禁止食品コード2: str = ""
    使用禁止食品コード3: str = ""
    使用禁止食品コード4: str = ""
    使用禁止食品コード5: str = ""
    使用禁止食品コード6: str = ""
    使用禁止食品コード7: str = ""
    使用禁止食品コード8: str = ""
    使用禁止食品コード9: str = ""
    使用禁止食品コード10: str = ""
    使用禁止食品1: str = ""
    使用禁止食品2: str = ""
    使用禁止食品3: str = ""
    使用禁止食品4: str = ""
    使用禁止食品5: str = ""
    使用禁止食品6: str = ""
    使用禁止食品7: str = ""
    使用禁止食品8: str = ""
    使用禁止食品9: str = ""
    使用禁止食品10: str = ""
    フリーコメント: str = ""


class 栄養指導(DwhBaseModel):
    """栄養指導実施情報（1オーダーにつき1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    指導時年齢: int | None = None
    指導時月齢: int | None = None
    指導時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_指導日_: date = Field(date(1000, 1, 1), alias="検索日(指導日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    キャンセル日の定義: str = ""
    キャンセル日: date | None = None
    キャンセル理由: str = ""
    部門発生区分: str = ""
    入外区分: str = ""
    保険分類: str = ""
    診療科コード: str = ""
    診療科: str = ""
    病棟コード: str = ""
    病棟: str = ""
    栄養指導場所コード: str = ""
    栄養指導場所: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    部門連係ID: str = ""
    予約日: date | None = None
    予約開始時刻: time | None = None
    受付時刻: time | None = None
    予約終了時刻: time | None = None
    指導対象コード: str | None = None
    指導対象: str = ""
    栄養指導パターンコード: str = ""
    栄養指導パターン: str = ""
    依頼病名コード1: str | None = None
    依頼病名コード2: str | None = None
    依頼病名コード3: str | None = None
    依頼病名: str | None = None
    前回指導: str | None = None
    加算: str | None = None
    身長: str | None = None
    体重: str | None = None
    標準体重: str | None = None
    目標体重From: str | None = None
    目標体重To: str | None = None
    BMI: str | None = None
    エネルギー: str = ""
    蛋白質: str = ""
    脂質: str = ""
    炭水化物: str = ""
    食塩: str = ""
    カルシウム: str = ""
    鉄: str = ""
    リン: str | None = None
    水分: str = ""
    カリウムfrom: str = ""
    カリウムto: str = ""
    食事中水分: str = ""
    熱量構成P: str = ""
    熱量構成F: str = ""
    熱量構成C: str | None = None
    PS比: str | None = None
    今回の運動量コード1: str | None = None
    今回の運動量コード2: str | None = None
    今回の運動量コード3: str | None = None
    今回の運動量コード4: str | None = None
    今回の運動量コード5: str | None = None
    今回の運動量: str | None = None
    コメントコード1: str | None = None
    コメントコード2: str | None = None
    コメントコード3: str | None = None
    コメントコード4: str | None = None
    コメントコード5: str | None = None
    コメント: str | None = None


class 入院予約(DwhBaseModel):
    """入院予約情報（1オーダーにつき1レコード）."""

    ROW_ID: str = ""
    件数: int = 1
    シーケンスID: str = ""
    トランザクション名: str = ""
    キー1: str = ""
    キー2: str = ""
    キー3: str = ""
    キー4: str = ""
    キー5: str = ""
    キー6: str = ""
    キー7: int = 0
    キー8: int = 0
    キー9: date = date(1000, 1, 1)
    キー10: time = time(0, 0, 0)
    ETL更新日: date = date(1000, 1, 1)
    ETL更新時刻: time = time(0, 0, 0)
    匿名ID: str = ""
    施設コード: str = ""
    施設名: str = ""
    患者ID: str = ""
    患者番号: float = 0.0
    依頼時年齢: int | None = None
    依頼時月齢: int | None = None
    依頼時日齢: int | None = None
    性別: str = ""
    検索日の定義: str = ""
    検索日_入院予約日_: date = Field(date(1000, 1, 1), alias="検索日(入院予約日)")
    検索時刻: time = time(0, 0, 0)
    入力日の定義: str = ""
    入力日: date | None = None
    入力時刻: time | None = None
    更新日の定義: str = ""
    更新日: date | None = None
    更新時刻: time | None = None
    キャンセル日の定義: str = ""
    キャンセル日: date | None = None
    入外区分: str = ""
    診療科コード: str = ""
    診療科: str = ""
    オーナーの定義: str = ""
    オーナーID: str = ""
    オーナー: str = ""
    オーナー職種: str = ""
    サブオーナー1の定義: str = ""
    サブオーナー1ID: str = ""
    サブオーナー1: str = ""
    サブオーナー1職種: str = ""
    予定SEQ: int | None = None
    入院予約区分: str | None = None
    入院予約入力日: date | None = None
    入院希望日: date | None = None
    入院希望診療科コード: str | None = None
    入院希望診療科: str = ""
    希望病棟コード1: str | None = None
    希望病棟コード2: str | None = None
    希望病棟コード3: str | None = None
    希望病棟1: str | None = None
    希望病棟2: str | None = None
    希望病棟3: str | None = None
    希望病室タイプ: str | None = None
    希望ベッド: str | None = None
    差額ベッド希望有無: str | None = None
    食種コード: str = ""
    食種: str = ""
    食事開始日: date | None = None
    食事開始時刻: str | None = None
    紹介の有無: str | None = None
    前医療機関: str | None = None
    前診療科: str | None = None
    前医: str | None = None
    入院時病名コード: str | None = None
    入院時病名: str | None = None
    入院目的コード1: str | None = None
    入院目的1: str | None = None
    入院目的コード2: str | None = None
    入院目的2: str | None = None
    入院目的コード3: str | None = None
    入院目的3: str | None = None
    入院目的コメント: str | None = None
    入院方法コード: str | None = None
    入院方法: str | None = None
    手術予定日: date | None = None
    緊急タイプコード: str | None = None
    緊急タイプ: str | None = None
    優先順位: int | None = None
    優先順位設定日: date | None = None
    優先順位設定時間: time | None = None
    入院連絡: str | None = None
    ステータス: str | None = None

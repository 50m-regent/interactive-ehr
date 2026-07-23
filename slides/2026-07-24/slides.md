---
marp: true
theme: research
paginate: true
math: mathjax
title: "Interactive EHRの評価方針"
author: "平田 蓮"
lang: "ja"
---

<!-- _class: cover -->
<!-- _paginate: false -->

# Interactive EHRの
# 評価方針

###### 利用効果と提案機構を分けて検証する · 2026-07-24

#### 京都大学大学院 情報学研究科 · 平田 蓮

---

<!-- _class: summary citation -->

# 今回合意したい方針

| 評価 | 目的 |
| --- | --- |
| 利用評価 | 既存EHRより正確かつ少ない時間・操作で情報を得られるか |
| 技術評価 | タスクグラフを介したUI更新が正確で、関係のない部分を保持できるか |
| 解釈 | UIの利用効果と、提案機構としての価値を分けて示す |

> NISTIR 7804, 2012. DOI: 10.6028/NIST.IR.7804 · Cao et al., CHI 2025. DOI: 10.1145/3706598.3713285

---

<!-- _class: comparison citation -->

# タスク特化UIの効果はすでに評価されている

1. 先行研究

   ダッシュボードや問題指向表示により、
   情報取得時間、クリック、誤り、
   認知負荷が改善した例がある。

2. 本研究への示唆

   整理されたUIが既存EHRより効率的でも、
   それだけではタスクグラフの寄与を
   分離できない。

> Fuller et al., Applied Ergonomics, 2020. DOI: 10.1016/j.apergo.2020.103047 · Semanik et al., JAMIA, 2021. DOI: 10.1093/jamia/ocaa332 · Pollack and Pratt, JAMA Network Open, 2020. DOI: 10.1001/jamanetworkopen.2019.19301 · Fan et al., JAMIA, 2025. DOI: 10.1093/jamia/ocaf103

---

<!-- _class: comparison citation -->

# 既存EHR比較だけでは残る問題

1. 比較から示せること

   専門家が確認した提案UIで、
   同じ診療情報を取得するときの
   正確性、時間、操作数。

2. 比較だけでは示せないこと

   タスクグラフを介することで、
   要求変更を安全かつ局所的に
   UIへ反映できるか。

> Fuller et al., Applied Ergonomics, 2020. DOI: 10.1016/j.apergo.2020.103047 · Cao et al., CHI 2025. DOI: 10.1145/3706598.3713285

---

<!-- _class: architecture citation -->

# 評価を二つに分ける

1. 利用評価

   提案UIと既存EHRで、
   同じ情報確認課題を比較する。

2. 技術評価

   変更要求に対するUI更新を、
   自動ベンチマークで検証する。

3. 統合した主張

   利用時の効率と、変更可能な中間表現としての価値を
   それぞれの結果から説明する。

> Cao et al., CHI 2025. DOI: 10.1145/3706598.3713285

---

<!-- _class: comparison citation -->

# 既存EHRとの利用評価

1. 比較条件

   麻酔科術前外来の同じ情報確認課題を、
   提案UIと既存EHRで実施する。

   症例と提示順を入れ替える。

2. 評価指標

   有効性はタスク成功率。

   効率は成功試行の完了時間、
   クリック、画面遷移、スクロール。

> NISTIR 7804, 2012. DOI: 10.6028/NIST.IR.7804 · Fuller et al., 2020. DOI: 10.1016/j.apergo.2020.103047

---

<!-- _class: summary citation -->

# UI更新ベンチマークの研究質問

| 観点 | 問うこと |
| --- | --- |
| 変更 | 要求された情報、データ取得、表示が反映されるか |
| 保持 | 変更対象外の情報と安全条件が残るか |
| 追跡 | 臨床タスク、必要情報、DataNode、SQL、Widgetがつながるか |
| 実行 | スキーマ、SQL、UI描画が正常に動くか |

> Cao et al., CHI 2025. DOI: 10.1145/3706598.3713285

---

<!-- _class: flow citation -->

# 一つの評価ケースを構成する要素

1. 初期グラフ
2. 自然言語の\
   変更要求
3. 変更・保護・\
   禁止条件
4. 自動化した\
   合格判定

> Foster et al., TOPLAS, 2007. DOI: 10.1145/1232420.1232424 · He et al., Information and Software Technology, 2018. DOI: 10.1016/j.infsof.2018.07.010

---

<!-- _class: comparison citation -->

# 麻酔科T1〜T7から作る変更例

1. 単発の変更

   検査期間を1か月から6か月へ変更

   腎機能を表から時系列グラフへ変更

   心電図の結果をT5へ追加

2. 継続的な変更

   情報を追加した後に表示形式を変更

   関係のないT1〜T4を保持

   最後の変更を取り消して元へ戻す

> Foster et al., TOPLAS, 2007. DOI: 10.1145/1232420.1232424 · He et al., Information and Software Technology, 2018. DOI: 10.1016/j.infsof.2018.07.010

---

<!-- _class: summary citation -->

# ケース成功率を主要評価にする

| 判定 | 内容 |
| --- | --- |
| 成功 | 要求反映、非対象部分、安全条件、追跡、SQL、描画をすべて満たす |
| 失敗 | 安全上重要な欠落は他の成功項目と平均せず、ケース失敗とする |
| 副次評価 | 更新範囲の適合率・再現率、保持率、安定性、時間、生成コスト |
| 初期候補 | 単発変更24件程度、連続更新6系列程度。件数はまだ確定しない |

> He et al., Information and Software Technology, 2018. DOI: 10.1016/j.infsof.2018.07.010

---

<!-- _class: architecture citation -->

# 主張の範囲と次の作業

1. 主張できる範囲

   既存EHRとの情報取得効率と、
   UI更新の正確性・局所性・一貫性。

2. まだ主張しないこと

   臨床転帰、実患者への有効性、
   技術評価だけによるUX改善。

3. 次の作業

   ClinicalTaskGraphからScenarioGraphへの更新経路を固定し、
   専門家基準と従来EHRの操作経路を確定する。

> NISTIR 7804, 2012. DOI: 10.6028/NIST.IR.7804 · Cao et al., CHI 2025. DOI: 10.1145/3706598.3713285

---

<!-- _class: summary -->

# 参考文献

| 分類 | 文献 |
| --- | --- |
| EHR比較 | Fuller et al., 2020, 10.1016/j.apergo.2020.103047 ／ Semanik et al., 2021, 10.1093/jamia/ocaa332 |
| 可視化 | Pollack and Pratt, 2020, 10.1001/jamanetworkopen.2019.19301 ／ Fan et al., 2025, 10.1093/jamia/ocaf103 |
| 生成UI | Cao et al., CHI 2025, 10.1145/3706598.3713285 ／ Lowry et al., NISTIR 7804, 2012, 10.6028/NIST.IR.7804 |
| 更新検証 | Foster et al., 2007, 10.1145/1232420.1232424 ／ He et al., 2018, 10.1016/j.infsof.2018.07.010 |

---
marp: true
theme: research
paginate: true
math: mathjax
title: "対話的グラフ構造化を用いた診療記録のタスク駆動型可視化"
author: "平田 蓮"
lang: "ja"
---

<!-- _class: cover -->
<!-- _paginate: false -->

# 対話的グラフ構造化を用いた<br>診療記録のタスク駆動型可視化

###### Research Seminar · 2026-07-03

#### 京都大学大学院 情報学研究科 · 平田 蓮

---

<!-- _class: summary -->

# 研究テーマ

<div class="summary-list">
  <div class="summary-row"><span>背景</span><strong>電子カルテの膨大な情報量が、必要情報の探索負荷につながる</strong></div>
  <div class="summary-row"><span>目的</span><strong>タスクに必要な情報だけを提示し、診療時のUXを改善する</strong></div>
  <div class="summary-row"><span>方法</span><strong>ユーザのタスクをグラフ化し、データとUIを動的に構成する</strong></div>
</div>

---

<!-- _class: flow -->

# 課題 — 情報量ではなく探索過程に着目

<div class="flow-row">
  <div class="flow-step"><b>1</b><span>診療記録に<br>情報が分散</span></div>
  <div class="flow-arrow">›</div>
  <div class="flow-step"><b>2</b><span>必要情報を<br>画面横断で探索</span></div>
  <div class="flow-arrow">›</div>
  <div class="flow-step accent"><b>3</b><span><strong>認知・操作負荷</strong><br>が増加</span></div>
</div>

---

<!-- _class: flow -->

# 提案 — タスクを起点にUIまで構造化

<div class="flow-row">
  <div class="flow-step"><b>1</b><span>診療<br>タスク</span></div>
  <div class="flow-arrow">›</div>
  <div class="flow-step"><b>2</b><span>ScenarioGraph<br>を生成</span></div>
  <div class="flow-arrow">›</div>
  <div class="flow-step accent"><b>3</b><span>必要データと<br><strong>UIを生成</strong></span></div>
</div>

---

# システム構成

<div class="columns">
  <div class="panel">
    <h2>1 · Task Recognition</h2>
    <p>プロンプトやUI操作から、ユーザが達成したいタスクを表現する。</p>
  </div>
  <div class="panel accent">
    <h2>2 · Data Collection</h2>
    <p>ScenarioGraphが要求する項目を、ローカルDWHからSQLで取得する。</p>
  </div>
</div>

<div class="panel" style="margin-top: 28px;">
  <h2>3 · UI Generation</h2>
  <p>タスク・データ・ウィジェットの関係から、閲覧目的に合うUIを描画する。</p>
</div>

---

<!-- _class: progress -->

# 現在の実装

<div class="progress-list">
  <div><b>1</b><span><strong>ScenarioGraph</strong> JSONからStreamlit UIを描画</span></div>
  <div><b>2</b><span>CSVから構築したローカルSQLite DWHをSQLで参照</span></div>
  <div><b>3</b><span>Geminiによるグラフ生成と、編集内容の即時プレビュー</span></div>
  <div><b>4</b><span>慢性疾患外来・周術期シナリオで表示経路を検証</span></div>
</div>

---

# 修論に向けた実験計画

<div class="columns">
  <div class="panel">
    <h2>比較</h2>
    <p>従来の電子カルテ操作と、タスク駆動UIを用いた操作を比較する。</p>
    <p><strong>対象候補</strong><br>医師・薬剤師などの医療従事者</p>
  </div>
  <div class="panel accent">
    <h2>評価</h2>
    <p>完了時間、操作回数、情報探索、主観的認知負荷を測定する。</p>
    <p><strong>次の焦点</strong><br>効果検証を先行し、グラフ自動生成の必要性を判断する。</p>
  </div>
</div>

---

# 次の予定

<div class="timeline">
  <div class="current"><b>1 · シナリオ</b><br>有識者意見を反映</div>
  <div><b>2 · グラフ</b><br>比較条件を固定</div>
  <div><b>3 · 実験</b><br>操作・負荷を評価</div>
  <div><b>4 · 論文</b><br>結果を統合</div>
</div>

<p style="margin-top: 48px;"><strong>相談したい点:</strong> 認知負荷と作業効率を、どの指標の組み合わせで評価するか</p>

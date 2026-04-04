# Interactive EHR

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステム

## 概要

電子カルテの膨大な情報量による医療従事者の認知負荷を軽減するため、ユーザのタスクに基づいて適切な情報を抽出し、UIを動的に生成するシステム。

## セットアップ

```bash
uv sync
```

## 起動

```bash
uv run streamlit run src/interactive_ehr/app.py
```

## テスト

```bash
uv run pytest tests/ -v
```

## 構成

```
src/interactive_ehr/
  app.py          -- Streamlitエントリポイント
  models/         -- データモデル（タスクグラフ等）
  widgets/        -- UIウィジェット
  pages/          -- ページコンポーネント
```

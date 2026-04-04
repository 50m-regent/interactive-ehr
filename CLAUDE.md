# CLAUDE.md

このファイルはClaude Code (claude.ai/code) がこのリポジトリで作業する際のガイダンスです。

## プロジェクト概要

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステムの研究プロジェクト。

## 開発環境

- Python 3.12（`.python-version`で管理）
- `uv`でプロジェクト管理（`pyproject.toml`使用、`requirements.txt`なし）
- ライブラリ追加: `uv add <package>`（pyproject.tomlを直接編集しない）
- 開発用ライブラリ追加: `uv add --dev <package>`

## ルール

- README.mdは機能追加・構成変更時に適宜更新すること

## コマンド

- アプリ起動: `uv run streamlit run src/interactive_ehr/app.py`
- テスト実行: `uv run pytest tests/ -v`

## 外部リソース

- **Notionページ（情報集約）**: https://www.notion.so/338c165ad0ab80a9b84dc3d14430c593
  - プロジェクトに関する全情報をこのページに集約

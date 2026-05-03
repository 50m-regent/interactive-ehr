# AGENTS.md

このファイルは Codex がこのリポジトリで作業する際のガイダンスです。
Claude Code 向けの `CLAUDE.md` と同じ意図の指示を Codex 向けにまとめています。

## プロジェクト概要

タスクのグラフ構造化を用いたインタラクティブな電子カルテシステムの研究プロジェクトです。

## 開発環境

- Python 3.12 を使用します。バージョンは `.python-version` で管理されています。
- プロジェクト管理は `uv` と `pyproject.toml` を使用します。
- `requirements.txt` は使用しません。
- ライブラリ追加は `uv add <package>` を使います。
- 開発用ライブラリ追加は `uv add --dev <package>` を使います。
- 依存関係を追加・更新するときは `pyproject.toml` を手作業で直接編集せず、原則として `uv` コマンドを使います。

## 作業ルール

- 機能追加や構成変更をした場合は、必要に応じて `README.md` を更新します。
- 既存の実装・テスト・ディレクトリ構成に合わせて、変更範囲を必要最小限に保ちます。
- Python コードを変更した場合は、関連テストを実行します。
- 外部 API や秘密情報を扱う変更では、`.env.example` の更新が必要か確認します。

## よく使うコマンド

- アプリ起動: `uv run streamlit run src/interactive_ehr/app.py`
- テスト実行: `uv run pytest tests/ -v`
- パッケージ追加: `uv add <package>`
- 開発用パッケージ追加: `uv add --dev <package>`

## 外部リソース

- Notion ページ（情報集約）: https://www.notion.so/338c165ad0ab80a9b84dc3d14430c593
  - プロジェクトに関する全情報をこのページに集約しています。

## Claude から移行した設定について

`.claude/settings.local.json` にある `Bash(uv run:*)` などの許可設定は Claude Code 固有の形式です。
Codex では同じ JSON を直接利用しないため、このファイルでは運用ルールと標準コマンドとして反映しています。

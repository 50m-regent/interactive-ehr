# AGENTS.md

このファイルは Codex がこのリポジトリで作業する際のガイダンスです。
Claude Code 向けの `CLAUDE.md` と同じ意図の指示を Codex 向けにまとめています。
応答は日本語で行ってください。

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

- リポジトリを変更する前に対応するGitHub Issueを確認し、なければ目的、対象範囲、完了条件を記載したIssueを作成します。状態を変えない調査や閲覧だけの作業は対象外です。
- IssueとNotionのタスクまたは成果物を相互にリンクし、作業ブランチとPRも同じIssueへ関連付けます。
- 作業用ブランチを切り、変更、検証、コミット、push、Draft PR作成まで行います。
- PR本文にはIssueとNotionページのURLを記載します。統合によってIssueが完了する場合だけ`Closes #番号`を使い、作業が残る場合は`Refs #番号`を使います。
- 作業場所はこの`interactive-ehr/`だけとし、追加のcloneやworktreeを作りません。
- 複数のチャットで同時に変更せず、作業用ブランチを順番に切り替えます。
- CodexのチャットはLocalで開始し、worktreeで始めたチャットはLocalへHandoffしてから続けます。
- 未コミット変更がある場合はブランチを切り替えず、変更内容と担当中の作業を確認します。
- 実装、設計、構成、運用手順を変更した場合は、`README.md`を現在の状態に合わせます。
- 既存の実装・テスト・ディレクトリ構成に合わせて、変更範囲を必要最小限に保ちます。
- Python コードを変更した場合は、関連テストを実行します。
- 外部 API や秘密情報を扱う変更では、`.env.example` の更新が必要か確認します。
- 作業終了前に開いているIssueとPRを確認し、差分、検証結果、セルフレビューに問題がなければPRを統合します。重複や不要になったIssueとPRは、理由を残して閉じます。
- 倫理確認、専門家確認、外部レビュー、ユーザーの判断が残るPRは統合せず、必要な確認内容をIssue、PR、Notionへ記録します。
- 統合または終了後は、Notionのタスクと成果物の状態、IssueとPRのリンクを更新します。
- 研究原稿はLaTeXと生成PDFを管理し、DOCXは管理しません。

## よく使うコマンド

- アプリ起動: `uv run streamlit run src/interactive_ehr/app.py`
- テスト実行: `uv run pytest tests/ -v`
- 型チェック: `uv run ty check src/interactive_ehr/widgets src/interactive_ehr/evaluation src/interactive_ehr/provenance.py src/interactive_ehr/scenario_graph.py src/interactive_ehr/llm/gemini.py src/interactive_ehr/app.py`
- パッケージ追加: `uv add <package>`
- 開発用パッケージ追加: `uv add --dev <package>`

## 外部リソース

- Notion ページ（情報集約）: https://www.notion.so/338c165ad0ab80a9b84dc3d14430c593
  - プロジェクトに関する全情報をこのページに集約しています。

## Claude から移行した設定について

`.claude/settings.local.json` にある `Bash(uv run:*)` などの許可設定は Claude Code 固有の形式です。
Codex では同じ JSON を直接利用しないため、このファイルでは運用ルールと標準コマンドとして反映しています。

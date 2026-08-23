# 閉域ネットワークへのデプロイ手順(Linux + Docker)

Citrix Workspace 経由でアクセスする閉域ネットワーク内の Linux マシンで
interactive-ehr をデモ・評価用に動かすための手順書。

この手順は**インターネット接続を一切必要としません**。
必要なものは以下の2ファイルだけです。

| ファイル | 内容 |
|---|---|
| `interactive-ehr-amd64-20260824.tar.gz` | 最新UIを含むLinux AMD64 Dockerイメージ。データは合成サンプルのみ |
| `interactive-ehr-amd64-20260824.tar.gz.sha256` | 転送後の破損チェック用チェックサム |

## 0. 前提条件の確認

閉域マシンで以下を実行して確認する。

```bash
# CPU アーキテクチャが x86_64 (amd64) であること
uname -m
# → x86_64 と表示されれば OK(aarch64 の場合はこのイメージは動かない → 連絡してください)

# Docker が使えること
docker version
# → Client / Server 両方のバージョンが表示されれば OK
# permission denied の場合: sudo を付けるか、管理者に docker グループへの追加を依頼
```

## 1. ファイル転送

Citrix のドライブマッピングまたはファイル転送ポータルで
`interactive-ehr-amd64-20260824.tar.gz` と `.sha256` を閉域マシンの任意のディレクトリ
(例: `~/interactive-ehr/`)にコピーする。

### 転送ポータルにサイズ制限がある場合(分割転送)

持ち出し側(ローカル)で分割してから転送する:

```bash
# ローカル側: 200MB ごとに分割(part-aa, part-ab, ... ができる)
split -b 200m interactive-ehr-amd64-20260824.tar.gz part-

# 閉域側: 結合して元に戻す
cat part-* > interactive-ehr-amd64-20260824.tar.gz
```

### 転送後の整合性確認(必須)

```bash
cd ~/interactive-ehr
sha256sum -c interactive-ehr-amd64-20260824.tar.gz.sha256
# → interactive-ehr-amd64-20260824.tar.gz: OK と出れば転送成功
# FAILED の場合はファイルが壊れているので再転送する
```

## 2. イメージのロード

```bash
docker load -i interactive-ehr-amd64-20260824.tar.gz
# → Loaded image: interactive-ehr:latest と表示される
# (gzip のまま読み込めるので解凍は不要)

docker images interactive-ehr
# → REPOSITORY=interactive-ehr, TAG=latest の行があれば OK
```

`interactive-ehr:2026-08-24-ui` も同じイメージを指す固定タグとして読み込まれる。

## 稼働中のDWHを保持してUIだけを更新する

配布イメージには実患者情報を含めない。院内の稼働コンテナから検証済みDWHをバックアップし、新しいUIコンテナへ院内環境内で反映する。

### 現在のデータを退避する

```bash
mkdir -p /home/hirata/interactive-ehr-backups/20260824_ui_update
docker cp interactive-ehr:/app/data/dwh \
  /home/hirata/interactive-ehr-backups/20260824_ui_update/dwh
docker cp interactive-ehr:/app/data/dwh.sqlite \
  /home/hirata/interactive-ehr-backups/20260824_ui_update/dwh.sqlite
sha256sum /home/hirata/interactive-ehr-backups/20260824_ui_update/dwh.sqlite
```

バックアップの作成とハッシュの記録が終わるまで、現在のコンテナを停止しない。

### 新しいコンテナへ切り替える

```bash
docker stop interactive-ehr
docker rename interactive-ehr interactive-ehr-before-ui-update-20260824

docker create --name interactive-ehr \
  --restart unless-stopped \
  -p 8501:8501 \
  -e GEMINI_PROXY_URL=http://192.168.197.130:3000/api/gemini \
  interactive-ehr:2026-08-24-ui

docker cp \
  /home/hirata/interactive-ehr-backups/20260824_ui_update/dwh/. \
  interactive-ehr:/app/data/dwh
docker cp \
  /home/hirata/interactive-ehr-backups/20260824_ui_update/dwh.sqlite \
  interactive-ehr:/app/data/dwh.sqlite

docker start interactive-ehr
```

Geminiプロキシを使わない場合は `-e GEMINI_PROXY_URL=...` を省略する。

### 更新結果を確認する

```bash
sha256sum /home/hirata/interactive-ehr-backups/20260824_ui_update/dwh.sqlite
docker exec interactive-ehr sha256sum /app/data/dwh.sqlite
docker exec interactive-ehr /opt/venv/bin/python -c 'import urllib.request,sys; health=urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health",timeout=10); root=urllib.request.urlopen("http://127.0.0.1:8501",timeout=10); sys.stdout.write(f"health_status={health.status} root_status={root.status}\n")'
```

二つのハッシュが一致し、`health_status=200 root_status=200` になった後で画面を確認する。患者文脈、データ時点、情報源、取得条件が表示されない場合は利用を開始しない。

### 問題がある場合に元へ戻す

```bash
docker stop interactive-ehr
docker rename interactive-ehr interactive-ehr-failed-20260824
docker rename interactive-ehr-before-ui-update-20260824 interactive-ehr
docker start interactive-ehr
```

ロールバック後もヘルスURLと画面URLがHTTP 200になることを確認する。原因を確認するまで失敗したコンテナとバックアップを削除しない。

## 3. 起動

```bash
docker run -d --name interactive-ehr \
  --restart unless-stopped \
  -p 8501:8501 \
  -e GEMINI_PROXY_URL=http://192.168.197.130:3000/api/gemini \
  interactive-ehr:latest
```

`GEMINI_PROXY_URL` は閉域内のベンダー提供 Gemini プロキシの URL。
これを付けるとサイドバーの「タスクグラフ生成」が閉域内でも使える。
プロキシを使わない(表示・JSON編集のみの)場合は `-e` 行ごと省略してよい。

必要に応じて追加できる環境変数(省略時はカッコ内のデフォルト):

```
-e GEMINI_MODEL=gemini-2.5-flash-lite     # プロキシで使うモデル名
-e GEMINI_PROXY_MAX_OUTPUT_TOKENS=8192    # 生成が途中で切れる場合は増やす
-e GEMINI_PROXY_TEMPERATURE=0.2
-e GEMINI_PROXY_TIMEOUT=300               # 秒
```

起動確認:

```bash
docker ps --filter name=interactive-ehr
# STATUS が Up になっていること

docker logs interactive-ehr
# 「You can now view your Streamlit app in your browser.」が出れば起動完了
```

### 参考: 外部通信を完全に遮断して起動したい場合

アプリ自体はオフラインで完結しますが、コンテナのネットワークを
完全に切り離す運用が求められる場合は次のように起動する。
`--network none` はポート公開(`-p`)と併用できないため、
アクセスはコンテナ内からに限られる点に注意。

```bash
docker run -d --name interactive-ehr --network none interactive-ehr:latest
docker exec interactive-ehr python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8501/_stcore/health').read())"
# → b'ok' が返れば動作している
```

通常のデモ用途では `-p 8501:8501`(セクション3冒頭のコマンド)で問題ない。
このアプリが自発的に通信するのは「タスクグラフ生成」ボタン押下時の
Gemini プロキシ(閉域内)向けのみ。なお `--network none` では
プロキシにも到達できないため、生成機能は使えなくなる。

## 4. ブラウザでアクセス

- そのマシン上のブラウザ: **http://localhost:8501**
- 閉域内の別端末から: **http://<マシンのIPアドレス>:8501**
  - IP 確認: `hostname -I`
  - つながらない場合はマシンのファイアウォールで 8501/tcp を許可する
    (例: `sudo firewall-cmd --add-port=8501/tcp` または `sudo ufw allow 8501`)

画面が表示されたら、麻酔科術前外来の診療画面が出る。
画面上部に合成データ、情報源、最終データ日時、画面構成の作成元が表示されること、
各タスクの「情報源と取得条件」を開いて参照テーブルとSQLを確認できることを確認する。
左上からサイドバーを開くと、慢性疾患外来への切り替えと
「UI生成・編集ツール」内のScenarioGraph JSON編集ができる。

## 5. タスクグラフ生成(Gemini プロキシ)の確認

`GEMINI_PROXY_URL` を付けて起動した場合、サイドバーの「タスクグラフ生成」が
閉域内のプロキシ経由で動作する。事前にプロキシへの疎通を確認しておくとよい:

```bash
curl -s -X POST http://192.168.197.130:3000/api/gemini \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemini-2.5-flash-lite","maxOutputTokens":64,"temperature":0,"input":"1+1の答えだけをJSONで {\"answer\": 数値} の形で返して","jsonMode":true}'
# → {"answer": 2} のような JSON が返れば疎通 OK
```

コンテナの中からの疎通も確認できる:

```bash
docker exec interactive-ehr python -c "
import requests
r = requests.post('http://192.168.197.130:3000/api/gemini', json={
    'model': 'gemini-2.5-flash-lite', 'maxOutputTokens': 64,
    'temperature': 0, 'input': 'ping を JSON {\"pong\": true} で返して',
    'jsonMode': True}, timeout=60)
print(r.status_code, r.text[:200])
"
```

注意:
- プロキシ未設定(`-e GEMINI_PROXY_URL` なし)で「タスクグラフ生成」を押すと
  認証エラーになる。その場合はサンプルシナリオ表示と JSON 手動編集のみ使う。
- 生成された JSON が途中で切れてエラーになる場合は
  `-e GEMINI_PROXY_MAX_OUTPUT_TOKENS=32768` のように増やして起動し直す。
- 同梱データはすべて合成(ダミー)データであり、実患者情報は含まれない。

## 6. デモ中の微調整(コンテナ内でのコード編集)

イメージには nano / vim-tiny が入っており、Streamlit は
ファイル保存時に自動リロードする設定(`--server.runOnSave=true`)のため、
コンテナ内で直接コードを編集してその場で反映できる。

```bash
docker exec -it interactive-ehr nano /app/src/interactive_ehr/app.py
# 保存するとブラウザ側に「Source file changed」→ Rerun で反映

# シナリオ JSON の編集
docker exec -it interactive-ehr nano /app/data/scenarios/ito.json
```

注意: コンテナ内の編集はコンテナを削除(`docker rm`)すると消える。
残したい変更は `docker cp` でホスト側に吸い出しておく:

```bash
docker cp interactive-ehr:/app/src ./src-backup
```

## 7. 運用コマンド

```bash
docker stop interactive-ehr      # 停止
docker start interactive-ehr     # 再開
docker restart interactive-ehr   # 再起動(挙動がおかしい時)
docker logs -f interactive-ehr   # ログ追跡(Ctrl-C で抜ける)

# 完全に消してやり直す
docker rm -f interactive-ehr
docker run -d --name interactive-ehr --restart unless-stopped -p 8501:8501 interactive-ehr:latest
```

## 8. トラブルシュート

| 症状 | 対処 |
|---|---|
| `port is already allocated` | 8501 が使用中。`-p 8502:8501` に変えて起動し、ブラウザは `:8502` にアクセス |
| `exec format error` / 即終了 | アーキテクチャ不一致。`uname -m` が x86_64 か確認(§0) |
| `permission denied` (docker) | `sudo docker ...` にするか、docker グループ追加を依頼 |
| sha256 が FAILED | 転送中の破損。再転送。分割転送した場合は `cat part-*` の結合順を確認 |
| ブラウザで接続できない | `docker ps` で Up か確認 → `docker logs` でエラー確認 → 別端末からならファイアウォール(§4) |
| 画面は出るがデータが空 | `docker logs` に SQLite エラーがないか確認し、ログを添えて開発者に連絡 |

## 9. 秘密情報について

- このイメージには GCP 認証鍵(`key.json`)・`.env` は**含まれていない**
  (ビルド時に `.dockerignore` で除外済み)。
- 閉域環境に認証鍵を持ち込む必要はなく、**持ち込んではいけない**。

# TraceBench-EHR正式評価 v1.1.0

## 解釈の範囲

匿名化済みMIMIC-IV Demo上の決定的な技術評価であり、臨床上の安全性、使いやすさ、認知負荷、臨床転帰、実運用、他施設への一般化は評価しない。

## データと候補

- 分割: test
- 回答可能ケース: 934件
- 質問テンプレート: 134件
- 更新ペア: 763件

## 主要結果

| 条件 | 不整合流出率 | 件数 | 妥当更新受理率 | 件数 | 特定率 | 修復成功率 |
|---|---:|---:|---:|---:|---:|---:|
| local_checks | 100.0% | 763/763 | 100.0% | 763/763 | 0.0% | 0.0% |
| artifact_contracts | 48.1% | 367/763 | 100.0% | 763/763 | 50.7% | 97.7% |
| graph_contract | 0.0% | 0/763 | 100.0% | 763/763 | 100.0% | 100.0% |
| sidecar_contract | 0.0% | 0/763 | 100.0% | 763/763 | 100.0% | 100.0% |

## 条件間の対応差

| 指標 | 比較 | 差 | 95%区間 |
|---|---|---:|---:|
| unsafe_acceptance_rate | graph_contract − local_checks | -1.0000 | [-1.0000, -1.0000] |
| valid_acceptance_rate | graph_contract − local_checks | 0.0000 | [0.0000, 0.0000] |
| unsafe_acceptance_rate | graph_contract − artifact_contracts | -0.4810 | [-0.4956, -0.4653] |
| valid_acceptance_rate | graph_contract − artifact_contracts | 0.0000 | [0.0000, 0.0000] |
| unsafe_acceptance_rate | graph_contract − sidecar_contract | 0.0000 | [0.0000, 0.0000] |
| valid_acceptance_rate | graph_contract − sidecar_contract | 0.0000 | [0.0000, 0.0000] |

## 整合性確認

- 正解ラベルとの不一致: 0件
- グラフ契約と同じ内容を持つサイドカー契約の判定不一致: 0件

## データ管理

質問文、正解SQL、患者ID、患者単位の結果値は保存していません。ケースID、チェックサム、変異種類、判定結果、集計だけを記録しています。

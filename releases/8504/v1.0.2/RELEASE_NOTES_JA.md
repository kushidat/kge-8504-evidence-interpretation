# v1.0.2 緊急修正の配布ノート / 2026-10-28

新バージョンの目的は、固定1疾患／1マウスの履歴情報を汎用根拠と誤認させるリスクを止めることです。汎用SPARQL+LLM統合を完成させたと主張しません。

## 変更対象（実装）
- 新 Evidence モジュール `kge_evidence_bundle_readonly_v1_0_2.py`：単一疾患7JSON群と単一候補snapshotの読み込みを排除し、全選択疾患について未接続の状態と出典境界を返す。
- 新 Streamlit wrapper：旧固定症例のみの科学的課題パネル非表示、11タブの状態説明、版番号、GO数名称、TOP50 CSV出力、6状態表示を展開欄へ。
- 新 LLM prompt：T2D固有の文面を外し、候補固有外部情報が未接続なら正式・暫定評価をNot assessedに保つ。
- Provenanceや過去のT2D snapshotは旧v1.0.1原本に保持。新配布版には入れない。両者を統合済みとは称さない。

## 未完了
- Macでの実起動・UI・CSVの受領テストとGitHubリリース登録。
- 同条件の汎用SPARQL+LLM照合、候補別アレル／原著自動照合、汎用科学的課題生成。
- REG04 11項目の正式受入、研究室・他ホスト配備、科学的モデル評価・KGE順位形成因果の実証。


## RC2 follow-up from Mac preview
- User-reported Mac preview PASS: ALS node2vec rank1 RBRC-GSC0038, T2D node2vec rank1 RBRC-GSC0231, melanoma CompGCN and other listed checks.
- RC2 modifies Top50 filename metadata and corrects an obsolete F3/Medium explanatory caption only.
- RC2 Mac acceptance and GitHub publish remain pending.

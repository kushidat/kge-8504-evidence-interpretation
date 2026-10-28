# v1.0.2 緊急修正の配布ノート / 2026-10-28

新バージョンの目的は、固定1疾患／1マウスの履歴情報を汎用根拠と誤認させるリスクを止めることです。汎用SPARQL+LLM統合を完成させたと主張しません。

## 変更対象（実装）
- 新 Evidence モジュール `kge_evidence_bundle_readonly_v1_0_2.py`：単一疾患7JSON群と単一候補snapshotの読み込みを排除し、全選択疾患について未接続の状態と出典境界を返す。
- 新 Streamlit wrapper：旧固定症例のみの科学的課題パネル非表示、11タブの状態説明、版番号、GO数名称、TOP50 CSV出力、6状態表示を展開欄へ。
- 新 LLM prompt：T2D固有の文面を外し、候補固有外部情報が未接続なら正式・暫定評価をNot assessedに保つ。
- Provenanceや過去のT2D snapshotは旧v1.0.1原本に保持。新配布版には入れない。両者を統合済みとは称さない。

## 2026-10-28 Mac technical acceptance (verified from user-provided logs)

- RC2 preview port 18570: timestamped Top50 filename = PASS; obsolete F3/Medium caption removal = PASS.
- Previous v1.0.2 preview: ALS, T2D, melanoma CompGCN, GO/source tabs, CSV top50 ranks = PASS (user verified).
- Production cutover 8504: v1.0.1 stopped safely; RC2 started on port 8504; HTTP 200; PID 45690 reported at cutover. The PID is a historical observation and not an ongoing guarantee.
- Post-cutover on port 8504: v1.0.2 page = PASS, ALS node2vec rank 1 RBRC-GSC0038 = PASS, SPARQL+LLM NOT_CONNECTED = PASS.
- T2D node2vec rank 1 RBRC-GSC0231 preserved in the tested CSV.

## Scientific and release scope

- Release classification: private GitHub PRE-RELEASE for Mac localhost only. Not institutional or multi-user deployment.
- Historical T2D seven-JSON comparison was removed from the generic Evidence UI; no substitute generic SPARQL+LLM integration has been implemented. Display states explicitly show NOT_CONNECTED rather than negative scientific evidence.
- Fixed single-candidate allele/publication snapshot and deterministic F3/Medium proposal were removed from the generic UI. Formal and provisional F/HML remain NOT_ASSESSED.
- Frozen Train/GO and KGE rankings were not altered by the emergency scope correction.
- The scope incident remains OPEN; REG04 0/11 closed; PR #3 remains Draft and unmerged; the scientific review has NOT been accepted. No new scientific results are claimed.
- PRIMARY_TEST / TEST / WITHHELD embargo and access restrictions remain in force. This release does not change the repository's PRIVATE visibility.

## Provenance of GitHub source and asset

- Verified source snapshot in the v1.0.2 tag: `releases/8504/v1.0.2/` (the tag is created by the publisher from verified v1.0.1 commit with RC2 files added; it does NOT merge PR #3 or alter main).
- Distribution asset: `KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028.zip`, 523457 bytes.
- ZIP SHA256: `1c557f0a95bfeb13a0f76dcfffaddbf0be960a66037544b7ab6fe584819b066d`.
- Use the attached release ZIP for Mac installation; the auto-generated GitHub source archive by itself is not the standalone deployment package.

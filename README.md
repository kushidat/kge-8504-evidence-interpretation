# KGE 8504: Disease-to-mouse candidate evidence interpretation

Research application for reviewing candidate experimental mice ranked by
knowledge-graph embedding (KGE) methods. This repository records a
**Mac-local technical release**, not an institution-wide service and not
an experimental validation of candidate disease models.

**Current release:** [v1.0.2](https://github.com/kushidat/kge-8504-evidence-interpretation/releases/tag/v1.0.2)
(pre-release; Mac localhost only; technical acceptance on 2026-10-28).

**Source snapshot:** `v1.0.2` tag, under `releases/8504/v1.0.2/`.
The default branch (`main`) is not the source of the v1.0.2 distribution;
its existing development history is retained.

**Distribution:** download the attached `KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028.zip`
from the v1.0.2 release. Do not treat GitHub's automatically generated
source archive as a ready-to-run Mac installer. Follow the README and
SHA256 validation instructions included in the release ZIP. The release
asset SHA256 is:

```
1c557f0a95bfeb13a0f76dcfffaddbf0be960a66037544b7ab6fe584819b066d
```

## Functionality and boundaries

- Presents six frozen KGE ranking families: node2vec, TransE, RotatE,
  ComplEx, RDF2Vec and CompGCN.
- Displays evidence and provenance views using configured frozen Train/GO
  inputs and the selected disease/mouse. GO overlaps are descriptive;
  they do **not** establish what caused a candidate's KGE rank.
- Provides an export of the selected family's top 50 candidates, with
  a filename bearing the local JST date and time of button rendering.
- Generic SPARQL+LLM matched-mouse comparison is **NOT CONNECTED**. This
  must not be interpreted as a negative scientific finding or absence
  of relevant external data.
- Candidate-specific outside allele/strain/publication evidence and
  formal/provisional F1-F4 or High/Medium/Low assessments are **not
  assessed** in this general-release scope. There is no live LLM API
  call in this release.
- This version has not been verified as an institution-wide multi-user
  deployment. PRIMARY_TEST / TEST / WITHHELD embargoes remain active.

## Known incident: v1.0.1 scope misrepresentation

After the earlier technical acceptance, a serious scope incident was
recognized in v1.0.1. An existing SPARQL+LLM comparison displayed
seven saved JSON snapshots associated with type 2 diabetes
(`MONDO_0005148`), and a candidate-specific supporting snapshot was
limited to `RBRC-GSC0231`. These fixed-case sources were not a generic
cross-disease comparison and must not be presented as such.

**The incident remains OPEN.** v1.0.2 removes those fixed-case inputs
from the general Evidence user interface, stops the case-specific
F3/Medium provisional recommendation and clearly reports
unconnected/unassessed functions. It **does not** implement a new
cross-disease SPARQL+LLM comparison or establish biological validity.
Historical v1.0.1 artifacts remain intact for audit purposes.

## Verification and scientific interpretation

The user reported successful Mac previews involving ALS (`MONDO_0004976`),
type 2 diabetes (`MONDO_0005148`) and melanoma (`MONDO_0005105`,
CompGCN), and successful cutover to local port 8504. The v1.0.2 source
tag, private GitHub pre-release and downloaded-asset SHA256 were also
checked. These are **technical acceptance observations only**; they are
not scientific results and do not establish generalization to all
diseases or all experimental mouse strains.

The scientific question motivating this project is why specific KGE
methods assign high ranks to particular disease-mouse pairs, and
whether the resulting candidates have relevant independent biological
evidence. That causal ranking question is **not resolved by this
software release**.

## License and attribution

The project rightsholder has selected **CC BY 4.0** for the original
software and original published research documents. This also covers
the repository's original version/schedule Excel workbooks, Word
manuals and screenshots that the rightsholder has expressly approved
for publication. See [`LICENSE`](LICENSE) and the
[CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en).

When reusing original materials, cite this repository, the relevant
version and creators, link the license and indicate modifications.
Third-party dependencies and externally authored materials retain
their own licenses or rights. Publishing code does not release the
non-distributed PRIMARY_TEST / TEST / WITHHELD datasets.

## Repository governance

- Existing `main` history and prior tags/releases are preserved.
- Open Draft PRs (including PR #3) are separate and are **not** merged
  into this release by the publication-preparation work.
- GitHub visibility is controlled independently. Adding this README
  and LICENSE does **not** mean that the repository is already public.
- The release remains a Mac-local application; the public repository,
  if activated after the final audit, is a source and documentation
  publication rather than a hosted online application.

## Japanese release notes

The official v1.0.2 technical notes follow. They describe the actual
accepted Mac release and supersede the older pre-release/pending wording
inside the immutable distribution ZIP.

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

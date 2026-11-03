#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated 8504 evidence-interpretation wrapper candidate.

This wrapper does NOT copy or modify the official FX9B FIX1 source. It verifies
its exact SHA256 at runtime, imports it read-only, renders the existing audit UI,
then appends a candidate Evidence Bundle panel.

No release/promotion is implied by this file.
"""
from __future__ import annotations

# V0.7.1 isolated table sort: all absent ranks stay at bottom.
from kge_rank_nullsort_v0_7_1 import install_rank_comparison_renderer as _kge_install_nullsort_071
_kge_install_nullsort_071()

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from kge_evidence_bundle_readonly_v0_6 import build_evidence_bundle, llm_input_payload

BASE_8504 = (
    Path.home()
    / "projects/kge/bridge_node2vec_2026"
    / "streamlit_app__FX9B_GFINAL_AUDIT_CANDIDATE_V0_1_FIX1_20261009.py"
)
BASE_8504_SHA256 = "4de02002017698a3453b0567ddd44ea629945888fba3e57f05043e48aabd47ca"
WRAPPER_STATUS = "ISOLATED_CANDIDATE / NOT_RELEASED / OFFICIAL_8504_UNCHANGED"

LOCAL_DIR = Path(__file__).resolve().parent
LLM_PROMPT_PATH = LOCAL_DIR / "LLM_PROVISIONAL_PROMPT_V0_1_20261023.txt"
LLM_OUTPUT_SCHEMA_PATH = LOCAL_DIR / "LLM_PROVISIONAL_OUTPUT_SCHEMA_V0_1_20261023.json"
LLM_HANDOFF_PATH = LOCAL_DIR / "HANDOFF_TO_SPARQL_LLM_FOR_LLM_BROKER_20261023.md"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def import_verified_base():
    if not BASE_8504.is_file():
        raise RuntimeError(f"official FX9B FIX1 source not found: {BASE_8504}")
    observed = sha256_file(BASE_8504)
    if observed != BASE_8504_SHA256:
        raise RuntimeError(
            f"official FX9B FIX1 SHA mismatch: observed={observed} expected={BASE_8504_SHA256}"
        )
    spec = importlib.util.spec_from_file_location("fx9b_fix1_official_readonly", BASE_8504)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import verified FX9B FIX1")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def render_evidence_panel(base) -> None:
    active = str(st.session_state.get("fx9b_active_audit_query", "")).strip()
    if not active:
        return

    st.divider()
    st.header("候補Mouse 生物学的根拠（隔離candidate）")
    st.caption(
        "既存8504の凍結順位を変更せず、選択候補にread-only Evidence Bundleを重ねます。"
        "V0.6ではFrozen Train・固定GO evidence source・7版一致した既存SPARQL+LLM group-level evidenceに加え、"
        "MONDO_0005148 x RBRC-GSC0231に限り、固定candidate-specific external snapshotをread-only表示し、正式評価を変更せず決定論的provisional assessmentを併記します。"
    )
    st.code(
        "EVIDENCE_CANDIDATE=YES\n"
        "OFFICIAL_8504_MUTATION=NO\n"
        "GFINAL_RANK_MUTATION=NO\n"
        "PRIMARY_TEST/TEST/WITHHELD=NO\n"
        "NETWORK_RETRIEVAL=NO\n"
        "LLM_CALL=NO",
        language="text",
    )

    helper = base.verified_helper()
    disease_id = helper.normalize_mondo_id(active)
    loaded = helper.load_all_six_family_frames(disease_id)

    c1, c2 = st.columns([2, 1])
    with c1:
        family = st.selectbox("Evidence対象 family", options=list(base.FAMILIES), key="evidence_family")
    with c2:
        rank = int(
            st.number_input(
                "Evidence対象 final_rank",
                min_value=1,
                max_value=base.MOUSE_N,
                value=1,
                step=1,
                key="evidence_final_rank",
            )
        )

    df = loaded["frames"][family].copy()
    hit = df.loc[pd.to_numeric(df["final_rank"], errors="raise").astype(int) == rank]
    if len(hit) != 1:
        st.error(f"candidate identity failure: {family} rank={rank} count={len(hit)}")
        st.stop()
    row = hit.iloc[0]
    mouse_iri = str(row["mouse_iri"])
    prov = loaded["provenance"][family]
    ranking = {
        "family": family,
        "final_rank": int(row["final_rank"]),
        "gene_rank": str(row.get("gene_rank", "")),
        "phenotype_rank": str(row.get("phenotype_rank", "")),
        "integrated_rank": str(row.get("integrated_rank", "")),
        "route_state": str(loaded["route_state"]),
        "family_ranking_sha256": str(prov.get("family_ranking_sha256", "")),
    }

    try:
        with st.spinner("固定Evidence sourceをSHA検証し、候補単位Bundleをread-only生成しています。"):
            bundle = build_evidence_bundle(
                disease_iri=str(loaded["disease_iri"]),
                mouse_iri=mouse_iri,
                ranking=ranking,
            )
    except Exception as exc:
        st.error(f"EVIDENCE_FAIL_CLOSED: {type(exc).__name__}: {exc}")
        st.stop()

    st.success(
        f"EVIDENCE_BUNDLE_READONLY=PASS / {family} rank={rank} / {bundle['identity']['rbrc_id']}"
    )
    # V0.7.2 (isolated): verified Evidence-success scientific follow-up.
    # The v0.6 Evidence identity and frozen rank must all match the fixed case.
    _kge072_identity = bundle.get("identity", {}) if isinstance(bundle, dict) else {}
    _kge072_allowed = (
        str(_kge072_identity.get("disease_iri", "")) == "http://purl.obolibrary.org/obo/MONDO_0005148"
        and str(_kge072_identity.get("mouse_iri", "")) == "http://metadb.riken.jp/db/rikenbrc_mouse/RBRC-GSC0231"
        and str(_kge072_identity.get("rbrc_id", "")) == "RBRC-GSC0231"
        and str(family) == "node2vec"
        and str(rank) == "1"
        and bundle.get("ranking", {}).get("frozen_flag") is True
    )
    if _kge072_allowed:
        st.divider()
        # HEADERFIX1: the already-invoked V0.7 follow-up helper renders the
        # science-question heading. A second st.subheader() here previously
        # produced the duplicate V0.7 / V0.7.2 headings in the Mac browser.
        # Keep a non-heading V0.7.2 status label until the helper source is
        # independently inspected and its own heading can be corrected.
        st.caption("隔離V0.7.2：固定症例の読取専用Evidenceに基づく検証課題です。凍結順位への寄与は未実証であり、モデルの採否は研究者が判断します。")
        from kge_candidate_research_next_steps_v0_7_2_labelonlyfix1 import render_followup_panel_from_verified_input as _kge072_render
        _kge072_render(
            expected_disease_iri="http://purl.obolibrary.org/obo/MONDO_0005148",
            expected_mouse_iri="http://metadb.riken.jp/db/rikenbrc_mouse/RBRC-GSC0231",
            expected_family="node2vec",
            expected_rank=1,
        )
    else:
        st.caption("追加検証課題はMONDO_0005148 × node2vec第1位RBRC-GSC0231の確認済み固定症例のみに対応します。")

    tabs = st.tabs([
        "要約", "元トリプル", "構造経路", "GO:疾患関連共有", "GO:Mouse全注釈",
        "既存SPARQL+LLM", "系統・アレル", "原著", "評価", "Provenance", "LLM暫定評価",
    ])

    with tabs[0]:
        gc = bundle["go_context"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("疾患関連Gene数", int(gc["disease_gene_count"]))
        c2.metric("Mouse GO term数", int(gc["candidate_go_count"]))
        c3.metric("疾患Gene-linked GO数", int(gc["disease_gene_linked_go_count"]))
        c4.metric("共有GO数", int(gc["shared_go_count"]))
        if (
            str(bundle["identity"].get("rbrc_id", "")) != "RBRC-GSC0231"
            and any(
                "RBRC-GSC0231" in str(note)
                for note in bundle["unproven_scope"]
            )
        ):
            st.info(
                "表示上の注意：以下のunproven_scopeに出てくるRBRC-GSC0231は、"
                "別途確認した固定症例の証拠適用範囲を説明しています。"
                "現在選択中のMouseにGckアレルや高血糖の根拠を割り当てた意味ではありません。"
                "この候補自身の根拠は『系統・アレル』タブのcandidate_specific_claimと"
                "allele_identity／phenotypeで確認してください。未評価は陰性の証明ではありません。"
            )
        st.json({
            "identity": bundle["identity"],
            "ranking": bundle["ranking"],
            "scientific_interpretation_status": "PARTIAL_EVIDENCE_ONLY_NOT_RANK_EXPLANATION",
            "unproven_scope": bundle["unproven_scope"],
        })

    with tabs[1]:
        st.warning(
            "ここは『候補Mouseが疾患を直接支持する根拠』ではなく、固定sourceから読んだ元トリプルです。"
            "candidate / linking / disease-context を分けて表示します。"
        )
        for label, key in (
            ("Candidate intrinsic source edges", "candidate_intrinsic"),
            ("Candidate linking source edges", "candidate_linking"),
            ("Disease-context source edges", "disease_context"),
        ):
            st.markdown(f"**{label}**")
            df0 = _frame(bundle["source_edges"][key])
            if df0.empty:
                st.info("該当source edgeなし。欠損を生物学的陰性とは解釈しません。")
            else:
                st.dataframe(df0, width="stretch", hide_index=True)

    with tabs[2]:
        indirect = _frame(bundle["structural_paths"])
        if indirect.empty:
            st.info("固定Train上で候補Mouseから対象疾患へ到達する表示対象structural pathはありません。")
        else:
            st.dataframe(indirect, width="stretch", hide_index=True)
        st.warning("表示する経路は構造的接続です。KGEがその経路を理由として順位を付けたことを示しません。")

    with tabs[3]:
        gc = bundle["go_context"]
        st.caption(
            "疾患側は直接Disease→GO注釈ではありません。Frozen Trainで疾患に結び付くGeneと、"
            "固定GO summaryのgene supportをread-only交差したpost-hoc contextです。"
        )
        shared = _frame(gc["shared_candidate_disease_gene_go"])
        if shared.empty:
            st.info("候補Mouse GOと疾患Gene-linked GOのexact共有はありません。これは生物学的無関係の証明ではありません。")
        else:
            st.dataframe(shared, width="stretch", hide_index=True)
        st.warning("共有GOは順位形成の因果証拠ではなく、GO一致だけからH/M/Lを自動変更しません。")

    with tabs[4]:
        go = _frame(bundle["go_context"]["candidate_mouse_go"])
        if go.empty:
            st.info("固定GO summaryにこのMouseの行はありません。欠損を生物学的陰性とは解釈しません。")
        else:
            st.dataframe(go, width="stretch", hide_index=True)
        st.caption("これは候補MouseのGO注釈一覧です。疾患特異的支持そのものではありません。")

    with tabs[5]:
        hist = bundle["historical_sparql_llm_evidence"]
        if hist.get("status") == "CONSENSUS_7_OF_7":
            st.success("HISTORICAL_SPARQL_LLM_CONSENSUS=PASS_7_OF_7")
        elif hist.get("status") == "NO_GROUP_MATCH":
            st.info("この候補は固定7版のmatched-Mouse groupには含まれていません。")
        else:
            st.info("固定historical Evidenceの対象scope外です。")
        st.json(hist)
        st.warning("これはhistorical group-level evidenceです。候補固有のアレル・表現型実証・原著・KGE順位理由を証明しません。")

    with tabs[6]:
        st.json(bundle["strain_and_allele"])

    with tabs[7]:
        st.json(bundle["external_papers"])

    with tabs[8]:
        assessment = bundle["assessment"]
        formal = assessment.get("formal_assessment_boundary", {})
        provisional = assessment.get("provisional_assessment", {})

        st.warning(
            "正式評価は変更していません。F1–F4=Not assessed、H/M/L=Not assessed、review_status=unreviewedのままです。"
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("正式 F1–F4", str(formal.get("f_class", "Not assessed")))
        c2.metric("正式 H/M/L", str(formal.get("hml", "Not assessed")))
        c3.metric("正式 review", str(formal.get("review_status", "unreviewed")))

        if provisional.get("status") == "PROVISIONAL_RULE_BASED_NOT_EXPERT_REVIEWED":
            st.info(
                "以下はEvidence Bundleから決定論的に生成した暫定提案です。LLM出力でも専門家レビューでもありません。"
            )
            p1, p2 = st.columns(2)
            p1.metric("暫定 F1–F4 提案", str(provisional.get("proposed_f_class")))
            p2.metric("暫定 H/M/L 提案", str(provisional.get("proposed_hml")))
        else:
            st.info("この候補にはV0.6暫定評価ルールを適用できるcandidate-specific Evidenceがありません。")

        st.json({
            "formal_assessment_boundary": formal,
            "provisional_assessment": provisional,
            "stock_phenotype": assessment.get("stock_phenotype"),
            "source_independence": assessment.get("source_independence"),
            "llm_provisional_status": assessment.get("llm_provisional_status"),
            "rules": assessment.get("rules"),
        })
        st.caption("F1–F4、H/M/L、stock phenotype、source independence、KGE順位因果は別変数です。単一スコア化しません。")

    with tabs[9]:
        st.json(bundle["provenance"])

    with tabs[10]:
        st.warning(
            "V0.6ではLLM APIを呼びません。ここでは固定Evidence入力・固定prompt・期待JSON schemaを生成するだけです。"
            "API keyの読取・保存・復号は行いません。評価タブのF3/Mediumは決定論的暫定提案であり、LLM出力・専門家評価ではありません。"
        )
        for pth, label in ((LLM_PROMPT_PATH, "prompt"), (LLM_OUTPUT_SCHEMA_PATH, "output schema"), (LLM_HANDOFF_PATH, "handoff")):
            if not pth.is_file():
                st.error(f"LLM_PREP_FAIL_CLOSED: missing {label}: {pth}")
                st.stop()

        llm_payload = llm_input_payload(bundle)
        prompt_text = LLM_PROMPT_PATH.read_text(encoding="utf-8")
        schema_obj = json.loads(LLM_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
        handoff_text = LLM_HANDOFF_PATH.read_text(encoding="utf-8")

        payload_bytes = json.dumps(llm_payload, ensure_ascii=False, indent=2).encode("utf-8")
        prompt_bytes = prompt_text.encode("utf-8")
        schema_bytes = json.dumps(schema_obj, ensure_ascii=False, indent=2).encode("utf-8")

        request_manifest = {
            "status": "LLM_PREP_ONLY_NO_API_CALL",
            "candidate_identity": {
                "disease_iri": bundle["identity"]["disease_iri"],
                "mouse_iri": bundle["identity"]["mouse_iri"],
                "family": bundle["ranking"]["family"],
                "final_rank": bundle["ranking"]["final_rank"],
            },
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "output_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
            "network_retrieval": False,
            "llm_call": False,
            "api_key_access": False,
            "formal_assessment_mutation": False,
            "expert_review_required": True,
        }
        st.success("LLM_PREP_PACKAGE=PASS / API_CALL=NO / API_KEY_ACCESS=NO")
        st.json(request_manifest)

        with st.expander("固定LLM prompt", expanded=False):
            st.code(prompt_text, language="text")
        with st.expander("期待LLM出力JSON schema", expanded=False):
            st.json(schema_obj)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "固定入力JSON", payload_bytes,
                file_name=f"EVIDENCE_LLM_INPUT__{disease_id}__{family}__rank{rank}__{bundle['identity']['rbrc_id']}.json",
                mime="application/json", key="evidence_llm_payload_download", on_click="ignore",
            )
        with c2:
            st.download_button(
                "固定prompt", prompt_bytes,
                file_name="LLM_PROVISIONAL_PROMPT_V0_1_20261023.txt",
                mime="text/plain", key="evidence_llm_prompt_download", on_click="ignore",
            )
        with c3:
            st.download_button(
                "出力schema", schema_bytes,
                file_name="LLM_PROVISIONAL_OUTPUT_SCHEMA_V0_1_20261023.json",
                mime="application/json", key="evidence_llm_schema_download", on_click="ignore",
            )

        st.download_button(
            "SPARQL+LLM担当への接続引継ぎ文", handoff_text.encode("utf-8"),
            file_name="HANDOFF_TO_SPARQL_LLM_FOR_LLM_BROKER_20261023.md",
            mime="text/markdown", key="evidence_llm_handoff_download", on_click="ignore",
        )


def main() -> None:
    try:
        base = import_verified_base()
    except Exception as exc:
        st.error(f"BASE_IDENTITY_FAIL_CLOSED: {type(exc).__name__}: {exc}")
        st.stop()
        return

    # Render official FX9B FIX1 behavior first. The official source is imported only
    # after exact SHA verification and is never written by this wrapper.
    base.render()
    render_evidence_panel(base)


if __name__ == "__main__":
    main()

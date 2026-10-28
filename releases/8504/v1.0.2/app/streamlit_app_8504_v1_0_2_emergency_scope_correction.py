#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""8504 v1.0.2 Mac-local emergency scope-correction wrapper.

This wrapper does NOT copy or modify the official FX9B FIX1 source. It verifies
its exact SHA256 at runtime, imports it read-only, renders the existing audit UI,
then appends a candidate Evidence Bundle panel.

Candidate-level historic and external resources are NOT CONNECTED.
Fixes misleading fixed-single-case presentation without asserting generic integration.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import re

# V0.7.1 isolated table sort: all absent ranks stay at bottom.
from kge_rank_nullsort_v0_7_1 import install_rank_comparison_renderer as _kge_install_nullsort_071
_kge_install_nullsort_071()

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd

import streamlit as st

from kge_evidence_bundle_readonly_v1_0_2 import build_evidence_bundle, llm_input_payload
from kge_verified_ranking_contract_v0_1 import verify_official_loaded_row_trusted
from kge_provisional_llm_output_gate_v0_1 import validate_provisional_llm_response

BASE_8504 = (
    Path.home()
    / "projects/kge/bridge_node2vec_2026"
    / "streamlit_app__FX9B_GFINAL_AUDIT_CANDIDATE_V0_1_FIX1_20261009.py"
)
BASE_8504_SHA256 = "4de02002017698a3453b0567ddd44ea629945888fba3e57f05043e48aabd47ca"
WRAPPER_STATUS = "V1_0_2_RC2_MAC_LOCAL_EMERGENCY_SCOPE_CORRECTION / SCIENTIFIC_ASSESSMENT_NOT_ACCEPTED"

LOCAL_DIR = Path(__file__).resolve().parent
LLM_PROMPT_PATH = LOCAL_DIR / "LLM_PROVISIONAL_PROMPT_V1_0_2_20261028.txt"
LLM_OUTPUT_SCHEMA_PATH = LOCAL_DIR / "LLM_PROVISIONAL_OUTPUT_SCHEMA_V0_1_20261023.json"
LLM_HANDOFF_PATH = LOCAL_DIR / "HANDOFF_TO_SPARQL_LLM_FOR_LLM_BROKER_20261023.md"

# Review-only proposal: enforce byte-identity before labeling LLM prep as PASS.
# The three expected digests are from the frozen FIX8 distribution archive.
PINNED_LLM_PREP_ASSET_SHA256 = {
    "prompt": 'e62fe1f1a5bbfee56f4cc791c408958eaf7a874bad182373239d3acbfae08284',
    "output schema": "a1f88e3036463a356b8101008fedb900adbc108aa247bb5544cd5a7070449c90",
    "handoff": "25bd0cef11eaa031baaabbd9b7ac7cec8c0c9a2b215f1ee29ae04fe98d8cd069",
}


def _pinned_llm_prep_bytes(path: Path, asset: str) -> bytes:
    raw = path.read_bytes()
    observed = hashlib.sha256(raw).hexdigest()
    expected = PINNED_LLM_PREP_ASSET_SHA256[asset]
    if observed != expected:
        raise RuntimeError(
            f"LLM_PREP_ASSET_SHA_MISMATCH: {asset}; observed={observed}; expected={expected}"
        )
    return raw


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


def top50_csv_from_verified_frame(loaded, family: str) -> bytes:
    # Caller must first validate the selected 5,892-row frame with the verified
    # ranking authority. This helper is bounded to exactly ranks 1..50.
    frame = loaded["frames"][family]
    numeric = pd.to_numeric(frame["final_rank"], errors="raise")
    top = frame.assign(__rank_sort=numeric).sort_values("__rank_sort", kind="mergesort").head(50)
    if len(top) != 50 or list(top["__rank_sort"].astype(int)) != list(range(1, 51)):
        raise RuntimeError("TOP50_CONTRACT_FAILED")
    return top.drop(columns=["__rank_sort"]).to_csv(index=False).encode("utf-8-sig")


def top50_export_filename(disease_id: str, family: str, when: datetime | None = None) -> str:
    """Export timestamp: button-render time in Asia/Tokyo, not click time."""
    if not re.fullmatch(r"MONDO_[0-9]+", disease_id):
        raise ValueError("INVALID_DISEASE_ID_FOR_CSV_NAME")
    if not re.fullmatch(r"[A-Za-z0-9_]+", family):
        raise ValueError("INVALID_FAMILY_FOR_CSV_NAME")
    instant = when if when is not None else datetime.now(ZoneInfo("Asia/Tokyo"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("EXPORT_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    suffix = instant.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d_%H%M%S_JST")
    return f"KGE_8504_{disease_id}_{family}_TOP50_{suffix}.csv"


def render_evidence_panel(base) -> None:
    active = str(st.session_state.get("fx9b_active_audit_query", "")).strip()
    if not active:
        return

    st.divider()
    st.header("候補マウスの生物学的根拠を確認（参考情報）")
    st.caption(
        "この画面では、KGEが提示した候補マウスについて、保存済みの遺伝子・表現型・GO情報を確認できます。"
        "候補マウスの順位は変更しません。GOは遺伝子・表現型を補う参考情報です。"
        "SPARQL+LLMでの同条件の検索結果照合と、候補固有の外部系統・文献情報の取得は未実装です。"
        "正式な科学的評価やKGE順位形成の原因の証明は行いません。"
    )
    st.warning(
        "【v1.0.2 緊急修正】前版でT2Dの過去資料と単一候補の外部資料を固定読込していた部分を、"
        "汎用的な検索結果と誤認させないため無効化しました。すべての疾患で同じ表示範囲を適用します。"
        "未接続は『検索結果なし』『科学的根拠なし』という意味ではありません。"
    )
    with st.expander("データ・動作範囲の詳細（運用情報）", expanded=False):
        st.code(
            "EVIDENCE_CANDIDATE=YES\n"
            "OFFICIAL_8504_MUTATION=NO\n"
            "GFINAL_RANK_MUTATION=NO\n"
            "PRIMARY_TEST/TEST/WITHHELD=NO\n"
            "NETWORK_RETRIEVAL=NO\n"
            "LLM_CALL=NO", language="text",
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

    try:
        # FIX6 F06: recheck the official 8504 source bytes and independently
        # inspect one row in its verified loader's 5,892-candidate frame.
        ranking, ranking_receipt, trusted_ranking_authority = verify_official_loaded_row_trusted(
            loaded=loaded, family=family, final_rank=rank
        )
        mouse_iri = ranking_receipt["mouse_iri"]
        with st.spinner("固定Evidence sourceをSHA検証し、候補単位Bundleをread-only生成しています。"):
            bundle = build_evidence_bundle(
                disease_iri=str(loaded["disease_iri"]),
                mouse_iri=mouse_iri,
                ranking=ranking,
                ranking_verification_receipt=ranking_receipt,
                trusted_ranking_authority=trusted_ranking_authority,
            )
    except Exception as exc:
        st.error(f"EVIDENCE_FAIL_CLOSED: {type(exc).__name__}: {exc}")
        st.stop()

    st.success(
        f"固定根拠データの読取り検証=PASS / {family} / 順位{rank} / {bundle['identity']['rbrc_id']}"
    )
    st.caption("これは入力の技術的な検証結果です。生物学的妥当性、順位形成の原因、SPARQL検索での検出を保証しません。")
    # Only the verified 5,892-row frame is used; the download is explicitly Top50.
    csv_bytes = top50_csv_from_verified_frame(loaded, family)
    st.download_button(
        "選択手法の上位50候補をCSV保存",
        csv_bytes,
        file_name=top50_export_filename(disease_id, family),
        mime="text/csv", key="kge_8504_v102_top50_csv", on_click="ignore",
    )
    st.caption("このCSVは画面表示用の上位50候補のみです。5,892件全順位の原本TSVではありません。")
    st.caption('CSV名の時刻は日本時間(JST)のボタン表示時刻です。クリック時刻とは限りません。')
    st.info("『次の科学的検証課題の自動提案』は汎用機能として未実装です。単一固定症例専用の前版パネルは起動しません。")

    tabs = st.tabs([
        "要約", "元トリプル", "構造経路", "GO:疾患関連共有", "GO:Mouse全注釈",
        "既存SPARQL+LLM", "系統・アレル", "原著", "評価", "Provenance", "LLM暫定評価",
    ])

    with tabs[0]:
        gc = bundle["go_context"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("疾患関連Gene数", int(gc["disease_gene_count"]))
        c2.metric("Mouse GO term数", int(gc["candidate_go_count"]))
        c3.metric("疾患関連遺伝子に基づくGO種類数", int(gc["disease_gene_linked_go_count"]))
        c4.metric("共有GO数", int(gc["shared_go_count"]))
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
        if hist.get("status") != "NOT_CONNECTED_EQUAL_SCOPE_SPARQL_LLM":
            st.error("SPARQL+LLM接続状態の契約違反です。照合結果は表示しません。")
            st.stop()
        st.info(
            "【未実装・未接続】この疾患・この候補マウスに対応する既存SPARQL+LLMの"
            "検索結果との同条件照合は、現行v1.0.2では行っていません。"
            "情報がない／検索で見つからないという判断ではありません。"
        )
        st.json(hist)

    with tabs[6]:
        st.info("【未接続・未評価】候補固有の外部系統・アレル情報は現在読み込んでいません。未評価は陰性ではありません。")
        st.json(bundle["strain_and_allele"])

    with tabs[7]:
        st.info("【未接続・未評価】この候補に固有の原著文献照合は行っていません。論文が存在しないとの判定ではありません。")
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
            st.info("候補固有の外部根拠は未接続のため、暫定F/HMLは提案しません。正式評価も未評価です。")

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
            "LLMの実API呼出しは未実装です。ここではEvidence入力・固定prompt・期待JSON schemaを保存できるだけです。"
            'API keyの読取・保存・復号は行いません。候補固有の外部根拠は未接続のため、暫定F/HMLは提案しません。正式評価も未評価です。'
        )
        try:
            prompt_bytes = _pinned_llm_prep_bytes(LLM_PROMPT_PATH, "prompt")
            schema_bytes = _pinned_llm_prep_bytes(LLM_OUTPUT_SCHEMA_PATH, "output schema")
            handoff_bytes = _pinned_llm_prep_bytes(LLM_HANDOFF_PATH, "handoff")
            prompt_text = prompt_bytes.decode("utf-8")
            schema_obj = json.loads(schema_bytes.decode("utf-8"))
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            st.error(f"LLM_PREP_FAIL_CLOSED: {type(exc).__name__}: {exc}")
            st.stop()
            return

        llm_payload = llm_input_payload(bundle)
        payload_bytes = json.dumps(llm_payload, ensure_ascii=False, indent=2).encode("utf-8")

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

        # FIX6 F04: an optional local-only response validation. This does NOT
        # send an LLM request, save a response, or alter formal F/HML status.
        with st.expander("外部LLM応答の候補・出典照合（V0.6契約、任意）", expanded=False):
            st.caption(
                "形式・候補ID・出典IDを確認し、根拠の自動検証がない肯定的F/HML・疾患モデル評価をHOLDします。"
                "PASSは科学的真偽の確認ではありません。FIX8は未評価の出力だけを限定受理し、検証済みBundleとの同一プロセス結合を要求します。"
                "8510・API・BYOKには接続しません。"
            )
            st.info(
                "【入力A／F04・V0.6暫定評価】この欄は候補・出典・未評価状態を検査するV0.6専用です。"
                "JSONキー例：candidate_identity、proposed_f_class、proposed_hml。"
                "上部のV0.7『次の科学的検証を考える』にある研究課題解釈欄には投入しないでください。"
            )
            st.caption(
                "この入力欄のアプリ側上限は500 KiB（512,000バイト）です。"
                "Streamlitに『200 MB』と表示される場合も、500 KiBを超えるJSONは拒否します。"
            )
            uploaded = st.file_uploader(
                "暫定LLM評価JSON（V0.6 schema）", type=["json"],
                key="kge_v06_provisional_output_json_fix8"
            )
            if uploaded is not None:
                try:
                    if uploaded.size > 500 * 1024:
                        raise ValueError("LLM応答JSONが500KBを超えています")
                    response = json.loads(uploaded.getvalue())
                    result = validate_provisional_llm_response(
                        response=response,
                        input_payload=llm_payload,
                        pinned_schema_path=LLM_OUTPUT_SCHEMA_PATH,
                        trusted_ranking_authority=trusted_ranking_authority,
                    )
                    st.success("LLM_OUTPUT_SOURCE_BOUNDARY=PASS / 保守的な未評価状態のみ・科学的真偽は未検証")
                    st.json(result)
                except (OSError, ValueError, RuntimeError) as exc:
                    st.error(f"LLM_OUTPUT_SOURCE_BOUNDARY=HOLD: {type(exc).__name__}: {exc}")

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
                file_name="LLM_PROVISIONAL_PROMPT_V1_0_2_20261028.txt",
                mime="text/plain", key="evidence_llm_prompt_download", on_click="ignore",
            )
        with c3:
            st.download_button(
                "出力schema", schema_bytes,
                file_name="LLM_PROVISIONAL_OUTPUT_SCHEMA_V0_1_20261023.json",
                mime="application/json", key="evidence_llm_schema_download", on_click="ignore",
            )

        st.download_button(
            "SPARQL+LLM担当への接続引継ぎ文", handoff_bytes,
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
    st.sidebar.info("""8504 v1.0.2 RC2｜Mac限定緊急修正版

SPARQL+LLM汎用照合・候補固有外部情報：未接続

科学的機能受入：再審査中""")
    render_evidence_panel(base)


if __name__ == "__main__":
    main()

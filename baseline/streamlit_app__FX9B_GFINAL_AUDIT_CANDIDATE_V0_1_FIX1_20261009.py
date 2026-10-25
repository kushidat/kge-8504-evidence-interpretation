#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FX9B candidate: B-side frozen G-FINAL six-family, read-only audit.

Derived audit operations (Top-N sets, overlap/Jaccard) are descriptive only.
No training, score generation, rank modification, remote retrieval or legacy runners.
Fix1: retain audit request across Streamlit reruns, disable download-triggered rerun,
normalize heterogeneous provenance schemas, and use supported dataframe width.
The existing A APP, A helper, FX8B FIX1, FX8B FIX2 are never written here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

APP_VERSION = "FX9B-GFINAL-AUDIT-CANDIDATE-V0_1-FIX1-BROWSER-STATE-PROVENANCE"
APP_BUILD = "2026-10-09"
SOURCE_B_FIX2_SHA256 = "082cfa77cce37a0ce5a1b239af3bb75830c2ba3a19f226700b7b392364bded1b"
HELPER_SHA256 = "bb4ff6acdd48af00f70c157fb9776e9de4213694c67607c8040f790dc03a364c"
HELPER = (Path.home() / "projects/mondo_eval/kg-llm-kge-lab-deploy/apps/mouse-model-search/gfinal_readonly_source_v0_4.py")
FAMILIES = ("node2vec", "TransE", "RotatE", "ComplEx", "CompGCN", "RDF2Vec")
MOUSE_N = 5892
MOUSE_PREFIX = "http://metadb.riken.jp/db/rikenbrc_mouse/"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def verified_helper():
    """Import frozen A helper only after exact SHA verification; never import A APP."""
    if not HELPER.is_file() or sha256_file(HELPER) != HELPER_SHA256:
        raise RuntimeError("Frozen A-side helper absent or SHA256 mismatch (fail-closed)")
    spec = importlib.util.spec_from_file_location("fx9b_verified_gfinal_v04", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen helper")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if tuple(mod.ALL_FAMILIES) != FAMILIES or mod.MOUSE_N != MOUSE_N:
        raise RuntimeError("Frozen helper contract mismatch")
    return mod


def verify_payload(loaded: dict) -> dict[str, pd.DataFrame]:
    frames = loaded["frames"]
    if set(frames) != set(FAMILIES) or set(loaded["provenance"]) != set(FAMILIES):
        raise RuntimeError("Incomplete six-family result or provenance")
    reference = None
    for family in FAMILIES:
        df = frames[family]
        if len(df) != MOUSE_N or "mouse_iri" not in df or "final_rank" not in df:
            raise RuntimeError(f"{family}: invalid frozen frame shape")
        mice = df["mouse_iri"].astype(str)
        if mice.nunique() != MOUSE_N or not mice.str.startswith(MOUSE_PREFIX).all():
            raise RuntimeError(f"{family}: Mouse identity mismatch")
        ranks = pd.to_numeric(df["final_rank"], errors="raise")
        if not ranks.notna().all() or sorted(ranks.astype(int).tolist()) != list(range(1, MOUSE_N + 1)) or not (ranks == ranks.astype(int)).all():
            raise RuntimeError(f"{family}: ordinal rank integrity failure")
        if reference is None:
            reference = set(mice)
        elif set(mice) != reference:
            raise RuntimeError(f"{family}: Mouse universe parity failure")
        if not loaded["provenance"][family].get("family_ranking_sha256"):
            raise RuntimeError(f"{family}: source SHA metadata missing")
    if loaded["route_state"] not in {"GENE_ONLY", "PHENO_ONLY", "GENE_PHENO"}:
        raise RuntimeError("route_state invalid")
    return frames


def original_frozen_tsv(helper, family: str, disease_id: str, provenance: dict) -> bytes:
    """Read actual source bytes, not dataframe.to_csv; verify member/package identity."""
    loc = helper.locate_family_ranking_source(family, disease_id)
    expected = str(provenance["family_ranking_sha256"])
    if family in helper.BUNDLED_FAMILIES:
        archive = Path(loc["bundle_path"])
        if sha256_file(archive) != loc["bundle_sha256"]:
            raise RuntimeError(f"{family}: frozen bundle SHA mismatch")
        member = loc["member_path"]
        with zipfile.ZipFile(archive) as z:
            if member not in z.namelist():
                raise RuntimeError(f"{family}: bundle member missing")
            raw = z.read(member)
    else:
        path = Path(loc["family_ranking_path"])
        if sha256_file(path) != expected:
            raise RuntimeError(f"{family}: frozen package SHA mismatch")
        raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError(f"{family}: original TSV SHA mismatch")
    return raw


def comparison(frames: dict[str, pd.DataFrame], top_n: int):
    rank_maps = {}
    sets = {}
    for family in FAMILIES:
        df = frames[family]
        mp = dict(zip(df["mouse_iri"].astype(str), df["final_rank"].astype(int)))
        rank_maps[family] = mp
        sets[family] = {mouse for mouse, rank in mp.items() if rank <= top_n}
        if len(sets[family]) != top_n:
            raise RuntimeError(f"{family}: Top-N uniqueness failure")
    rows = []
    for mouse in sorted(set().union(*sets.values())):
        row = {"mouse_iri": mouse, "mouse_id": mouse.rsplit("/", 1)[-1]}
        for family in FAMILIES:
            rank = rank_maps[family][mouse]
            row[f"{family}_rank"] = rank if rank <= top_n else pd.NA
        row["methods_in_topN"] = sum(mouse in sets[x] for x in FAMILIES)
        rows.append(row)
    overlap = pd.DataFrame(index=FAMILIES, columns=FAMILIES, dtype=int)
    jaccard = pd.DataFrame(index=FAMILIES, columns=FAMILIES, dtype=float)
    for a in FAMILIES:
        for b in FAMILIES:
            intersect = len(sets[a] & sets[b]); union = len(sets[a] | sets[b])
            overlap.loc[a, b] = intersect
            jaccard.loc[a, b] = intersect / union if union else 0.0
    return pd.DataFrame(rows), overlap.astype(int), jaccard



def provenance_table(helper, loaded: dict, frames: dict[str, pd.DataFrame], disease_id: str) -> pd.DataFrame:
    """Present verified bundle/package identities with a common six-family schema.

    Paths are descriptive; family_ranking_sha256 identifies the exact TSV bytes,
    whereas artifact_sha256 identifies the ZIP transport for bundled families.
    Missing *inapplicable* family-specific fields are empty strings, not NaN.
    """
    rows = []
    for family in FAMILIES:
        provenance = loaded["provenance"][family]
        locator = helper.locate_family_ranking_source(family, disease_id)
        kind = str(locator.get("source_kind", ""))
        sha = str(provenance["family_ranking_sha256"])
        if (
            str(locator.get("disease_iri", "")) != loaded["disease_iri"]
            or str(locator.get("source_provider", "")) != "local_immutable_mirror"
            or str(provenance.get("source_kind", "")) != kind
        ):
            raise RuntimeError(f"{family}: displayed provenance identity mismatch")
        if family in helper.BUNDLED_FAMILIES:
            if kind != "gfinal_deterministic_bundle" or str(locator.get("member_sha256", "")) != sha:
                raise RuntimeError(f"{family}: bundled provenance SHA mismatch")
            artifact_path = str(locator["bundle_path"])
            artifact_sha = str(locator["bundle_sha256"])
            native_id = str(locator["bundle_id"])
            member_path = str(locator["member_path"])
        else:
            if kind != "verified_family_package" or str(locator.get("family_ranking_sha256", "")) != sha:
                raise RuntimeError(f"{family}: package provenance SHA mismatch")
            if str(locator.get("route_state", "")) != loaded["route_state"]:
                raise RuntimeError(f"{family}: provenance route mismatch")
            artifact_path = str(locator["family_ranking_path"])
            artifact_sha = sha
            native_id = str(locator["unit_id"])
            member_path = ""  # Not applicable to verified_family_package.
        rows.append({
            "family": family,
            "rows": len(frames[family]),
            "disease_iri": loaded["disease_iri"],
            "route_state": loaded["route_state"],
            "source_kind": kind,
            "source_provider": "local_immutable_mirror",
            "source_native_id": native_id,
            "source_artifact_path": artifact_path,
            "source_artifact_sha256": artifact_sha,
            "bundle_member_path": member_path,
            "family_ranking_sha256": sha,
        })
    return pd.DataFrame(rows)


def render():
    st.set_page_config(page_title="FX9B G-FINAL 六手法監査候補", layout="wide")
    st.title("Disease → Mouse：FX9B G-FINAL監査（候補／read-only）")
    st.caption("FX8B FIX2監査系からの独立候補。A-sideの凍結済みG-FINAL helperを使用。順位再計算・新規ranking生成なし。")
    disease = st.text_input("MONDO疾患ID／絶対IRI", value="MONDO_0005148", key="fx9b_disease_query")
    display_n = st.number_input("手法別表示行数", min_value=1, max_value=MOUSE_N, value=50)
    top_n = st.number_input("6手法比較Top-N", min_value=1, max_value=MOUSE_N, value=50)
    if st.button("凍結済み6手法をread-only監査", type="primary"):
        # Persist only the query, never unverified/cached ranking data.
        st.session_state["fx9b_active_audit_query"] = str(disease).strip()
    if not str(disease).strip() or st.session_state.get("fx9b_active_audit_query") != str(disease).strip():
        st.info("入力後、監査ボタンで取得します。起動時の自動ロードはありません。")
        return
    # On every render, reload and reverify the frozen helper and rankings.
    # A download or an unrelated widget rerun must not bypass integrity gates.
    try:
        helper = verified_helper()
        disease_id = helper.normalize_mondo_id(disease)
        loaded = helper.load_all_six_family_frames(disease_id)
        if loaded["disease_iri"] != helper.mondo_iri(disease_id):
            raise RuntimeError("disease identity mismatch")
        frames = verify_payload(loaded)
        summary, overlap, jaccard = comparison(frames, int(top_n))
    except Exception as exc:
        st.error(f"FAIL_CLOSED: {type(exc).__name__}: {exc}")
        st.stop()
        return
    st.success(f"SIX_FAMILY_FROZEN_SOURCE_INTEGRITY=PASS / route={loaded['route_state']} / 6 × {MOUSE_N} Mouse")
    st.caption("PASSは選択疾患についてのhelper検証・フレーム完全性を意味します。A/B実機parity、全疾患検証、browser QAを意味しません。")
    st.subheader("6手法 source identity / provenance")
    try:
        audit = provenance_table(helper, loaded, frames, disease_id)
    except Exception as exc:
        st.error(f"FAIL_CLOSED: provenance: {type(exc).__name__}: {exc}")
        st.stop()
        return
    st.caption("bundle／packageで固有項目が異なります。各手法のsource identityはfamily_ranking_sha256を含めて表示しています。")
    st.dataframe(audit, width="stretch", hide_index=True)
    st.subheader(f"Top-{int(top_n)}：6手法保存順位の比較")
    st.dataframe(summary, width="stretch", hide_index=True)
    st.markdown("**Pairwise overlap count**")
    st.dataframe(overlap, width="stretch")
    st.markdown("**Pairwise Jaccard**")
    st.dataframe(jaccard, width="stretch")
    st.subheader("手法別：元の凍結順位と候補詳細")
    tabs = st.tabs(list(FAMILIES))
    for tab, family in zip(tabs, FAMILIES):
        with tab:
            df = frames[family].sort_values("final_rank", key=lambda s: s.astype(int), kind="mergesort")
            st.dataframe(df.head(int(display_n)), width="stretch", hide_index=True)
            selected_rank = st.number_input(f"{family}: final_rank", min_value=1, max_value=MOUSE_N, value=1, key=f"rank_{family}")
            selected = df.loc[df["final_rank"].astype(int) == int(selected_rank)]
            if len(selected) != 1:
                st.error(f"{family}: final_rank uniqueness failure")
                st.stop()
            st.dataframe(selected, width="stretch", hide_index=True)
            with st.expander(f"{family}: 元TSVをSHA検証してダウンロード", expanded=False):
                try:
                    raw = original_frozen_tsv(helper, family, disease_id, loaded["provenance"][family])
                    st.code(json.dumps(loaded["provenance"][family], ensure_ascii=False, indent=2), language="json")
                    st.download_button("元のfamily_ranking.tsv", raw, file_name=f"{family}__{disease_id}__family_ranking.tsv", mime="text/tab-separated-values", key=f"download_{family}", on_click="ignore")
                except Exception as exc:
                    st.error(f"FAIL_CLOSED: {family} download withheld: {exc}")
    with st.expander("実行禁止境界"):
        st.code("GFINAL_SOURCE=LOCAL_IMMUTABLE_MIRROR\nSCIENTIFIC_EXECUTION=NO\nTRAINING=NO\nRESCORING=NO\nFAMILY_RERANK=NO\nCROSS_FAMILY_FUSION=NO\nPRIMARY_TEST_ACCESS=NO\nTEST_ACCESS=NO\nWITHHELD_ACCESS=NO\nINTEGRITY_FAILURE=FAIL_CLOSED")


if __name__ == "__main__":
    render()

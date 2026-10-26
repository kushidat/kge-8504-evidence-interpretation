#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only candidate Evidence Bundle adapter for KGE Mouse interpretation.

Scope (V0.6 isolated candidate):
- Reads only pinned Frozen Train and pinned GO derived evidence sources.
- Does not modify G-FINAL ranking, helper, source files, or production apps.
- Does not access PRIMARY_TEST / TEST / withheld, validation, or model training.
- Does not perform network retrieval or LLM calls.
- Historical SPARQL+LLM outputs are bound as a pinned 7-file consensus group-level context.
- A separately pinned, curated candidate-specific external evidence snapshot may be read
  for RBRC-GSC0231 only. It is not raw source bytes and does not imply release authority.

This module is an implementation candidate, not a frozen schema authority.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from kge_verified_ranking_contract_v0_1 import validate_receipt

SCHEMA_ID = "KGE_MOUSE_EVIDENCE_BUNDLE_DRAFT_V0_5_20261023"
IMPLEMENTATION_STATUS = "ISOLATED_CANDIDATE_NOT_RELEASED"

PROJECT_ROOT = Path.home() / "projects/kge/bridge_node2vec_2026"
TRAIN_EXPECTED_SHA256 = "9b9e5fab42f1754b2462a5a6dd77c44ee31ff3b21b2c8eda4d7b45f36242e806"
TRAIN_CANDIDATES = (
    PROJECT_ROOT / "work/kge_retrain_colab_20260829/benchmark_v1/primary_train.tsv",
    PROJECT_ROOT / "work/kge_retrain_colab_20260829/colab_phase1/benchmark/primary_train.tsv",
)
GO_DIR = PROJECT_ROOT / "data/derived/go_mouse_function/20260829_evidence"
GO_FILES = {
    "go_support_bridge": (
        GO_DIR / "go_support_bridge.tsv",
        "5d954d2aebee9b79ffa4e772715eb11965f6a0cafb9c0fa52c3bf2c338d5589b",
    ),
    "go_evidence_provenance": (
        GO_DIR / "go_evidence_provenance.tsv",
        "5db199cecc4cd16e385a9f673f8b0ceec0eddd3c0624d378d242d2b3b2739a02",
    ),
    "go_evidence_summary": (
        GO_DIR / "go_evidence_summary.tsv",
        "583bf67d02232903ba13cdae068727cab7a851ffb4ee13e20dcb50274eca68b3",
    ),
}

REL_MOUSE_GENE = "http://purl.org/rbrc/resource/relatedGene"
REL_DISEASE_HP = "https://w3id.org/biolink/vocab/has_phenotype"
REL_ORTHOLOGY = "https://w3id.org/biolink/vocab/orthologous_to"
GO_PREDICATES = {
    "http://purl.org/rbrc/resource/relatedBp": "BP",
    "http://purl.org/rbrc/resource/relatedMf": "MF",
    "http://purl.org/rbrc/resource/relatedCc": "CC",
}
MOUSE_PREFIX = "http://metadb.riken.jp/db/rikenbrc_mouse/"
GO_PREFIX = "http://purl.obolibrary.org/obo/GO_"
HP_PREFIX = "http://purl.obolibrary.org/obo/HP_"
MP_PREFIX = "http://purl.obolibrary.org/obo/MP_"


MONDO_EVAL_ROOT = Path.home() / "projects/mondo_eval"
HISTORICAL_SPARQL_LLM_FILES = (
    (MONDO_EVAL_ROOT / "outputs2/2026-05-26T22-50-13_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "924ef28519e369201d31f0760a9ca4d33b7547fc8bd8c8473eab01d81e9bbaf3"),
    (MONDO_EVAL_ROOT / "outputs2/2026-05-27T02-11-01_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "581221ff33815ab3a303fea1c979e5d0c18978fa0c7577097c971039cc6685c4"),
    (MONDO_EVAL_ROOT / "outputs2/2026-05-27T02-41-07_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "7d11c351d95949bc696c4336262308fadfa9d9c3f2e7d536f6c1d206c4d38477"),
    (MONDO_EVAL_ROOT / "outputs2/2026-05-27T03-00-48_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "a949137d9861e7e1b3cef2f02a60e2fc9d5ff5d2976d935c6a13d28c1e2f0ed7"),
    (MONDO_EVAL_ROOT / "outputs2/2026-06-03T15-56-03_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "fc274129eae0b1dd960f1b9f912f5eb84a5636cf812b7434688f40f18e595114"),
    (MONDO_EVAL_ROOT / "outputs2/2026-06-03T16-38-30_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "ae79d7f8c36b6472793a1ef3dd2d0467ee91a1ae13a3507086ba294cebcebae1"),
    (MONDO_EVAL_ROOT / "outputs2/2026-06-06T22-48-35_MONDO_0005148_RBRC-GSC0032_integrated_candidate_interpretation.json", "298eb6afdbf53f89715ff83fdde79f9c19863a88720c752185063f6ca8c47920"),
)
HISTORICAL_BOUND_DISEASE_IRI = "http://purl.obolibrary.org/obo/MONDO_0005148"

CANDIDATE_SNAPSHOT_PATH = PROJECT_ROOT / "isolated/kge_evidence_v0_6/RBRC_GSC0231_CANDIDATE_SPECIFIC_EVIDENCE_SNAPSHOT_V0_1_20261023.json"
# FIX5: external original path, exact SHA, no sibling/untracked copy required.
CANDIDATE_SNAPSHOT_EXPECTED_SHA256 = "2d26283d2340001ebfa2c80f77299e6d51dcc353c072f73ec31416c484a8a0d6"
CANDIDATE_SNAPSHOT_DISEASE_IRI = "http://purl.obolibrary.org/obo/MONDO_0005148"
CANDIDATE_SNAPSHOT_RBRC_ID = "RBRC-GSC0231"


HML_ALLOWED = {"High", "Medium", "Low", "Not assessed"}
F_ALLOWED = {"F1", "F2", "F3", "F4", "Not assessed"}
REVIEW_ALLOWED = {"unreviewed", "provisional", "expert_reviewed"}

PROVISIONAL_ASSESSMENT_RULESET_ID = "KGE_EVIDENCE_PROVISIONAL_ASSESSMENT_RULESET_V0_1_20261023"
PROVISIONAL_STATUS_ALLOWED = {
    "NOT_ASSESSED",
    "PROVISIONAL_RULE_BASED_NOT_EXPERT_REVIEWED",
}



def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@lru_cache(maxsize=32)
def _verify_file_cached(path_str: str, expected_sha256: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != expected_sha256:
        raise RuntimeError(
            f"evidence source SHA256 mismatch: {path} observed={observed} expected={expected_sha256}"
        )
    return {
        "path": str(path),
        "sha256": observed,
        "size_bytes": path.stat().st_size,
    }


def _verified(path: Path, expected_sha256: str) -> dict[str, Any]:
    # mtime/size changes cause a new cache key in normal app usage only after module reload;
    # exact SHA remains the authority and is always emitted into the bundle.
    return _verify_file_cached(str(path), expected_sha256)


def resolve_frozen_train() -> tuple[Path, dict[str, Any]]:
    errors: list[str] = []
    for p in TRAIN_CANDIDATES:
        if not p.is_file():
            errors.append(f"missing:{p}")
            continue
        try:
            meta = _verified(p, TRAIN_EXPECTED_SHA256)
            return p, meta
        except Exception as exc:  # fail-closed but allow alternate exact path
            errors.append(f"{p}:{type(exc).__name__}:{exc}")
    raise RuntimeError("Frozen Train exact source unresolved: " + " | ".join(errors))


@lru_cache(maxsize=1)
def load_frozen_train() -> tuple[pd.DataFrame, dict[str, Any]]:
    path, meta = resolve_frozen_train()
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=["s", "p", "o"],
        dtype=str,
        keep_default_na=False,
    )
    if list(df.columns) != ["s", "p", "o"] or len(df) == 0:
        raise RuntimeError("Frozen Train schema/read failure")
    if (df == "").any().any():
        raise RuntimeError("Frozen Train contains blank s/p/o in candidate reader")
    return df, meta


def _edge_records(df: pd.DataFrame, *, evidence_type: str, source_id: str) -> list[dict[str, Any]]:
    return [
        {
            "evidence_type": evidence_type,
            "subject_iri": str(r.s),
            "predicate_iri": str(r.p),
            "object_iri": str(r.o),
            "source_id": source_id,
            "source_row_number": int(idx) + 1,
        }
        for idx, r in df.iterrows()
    ]


def derive_train_evidence(train: pd.DataFrame, disease_iri: str, mouse_iri: str) -> dict[str, Any]:
    """Pure derivation from an already verified Train dataframe.

    The result reports structural paths only. It does not claim that a path caused a KGE rank.
    """
    if not disease_iri.startswith("http") or not mouse_iri.startswith(MOUSE_PREFIX):
        raise ValueError("absolute disease IRI and RBRC Mouse IRI required")

    mouse_gene = train[(train.s == mouse_iri) & (train.p == REL_MOUSE_GENE)].copy()
    mouse_genes = set(mouse_gene.o.astype(str))

    gene_disease = train[(train.s.isin(mouse_genes)) & (train.o == disease_iri)].copy()

    orth = train[(train.s.isin(mouse_genes)) & (train.p == REL_ORTHOLOGY)].copy()
    human_genes = set(orth.o.astype(str))
    human_gene_disease = train[(train.s.isin(human_genes)) & (train.o == disease_iri)].copy()

    disease_hp = train[(train.s == disease_iri) & (train.p == REL_DISEASE_HP) & (train.o.str.startswith(HP_PREFIX))].copy()
    hp_set = set(disease_hp.o.astype(str))
    hp_mp = train[(train.s.isin(hp_set)) & (train.o.str.startswith(MP_PREFIX))].copy()

    mouse_mp = train[(train.s == mouse_iri) & (train.o.str.startswith(MP_PREFIX))].copy()
    mouse_mp_set = set(mouse_mp.o.astype(str))
    shared_mp = sorted(mouse_mp_set & set(hp_mp.o.astype(str)))

    pheno_paths: list[dict[str, Any]] = []
    for mp in shared_mp:
        hp_edges = hp_mp[hp_mp.o == mp]
        mouse_edges = mouse_mp[mouse_mp.o == mp]
        for _, hm in hp_edges.iterrows():
            dh_edges = disease_hp[disease_hp.o == hm.s]
            for _, dh in dh_edges.iterrows():
                for _, mm in mouse_edges.iterrows():
                    pheno_paths.append(
                        {
                            "path_type": "DISEASE_HP_MP_MOUSE_STRUCTURAL",
                            "path_nodes": [str(dh.s), str(dh.o), str(hm.o), str(mm.s)],
                            "edge_iri": [str(dh.p), str(hm.p), str(mm.p)],
                            "direction_of_edges": ["forward", "forward", "reverse_to_Mouse"],
                            "path_length": 3,
                            "interpretation_boundary": "STRUCTURAL_ONLY_NOT_RANK_CAUSALITY",
                        }
                    )

    direct_gene_paths: list[dict[str, Any]] = []
    for _, mg in mouse_gene.iterrows():
        for _, gd in gene_disease[gene_disease.s == mg.o].iterrows():
            direct_gene_paths.append(
                {
                    "path_type": "MOUSE_GENE_DISEASE_STRUCTURAL",
                    "path_nodes": [str(mg.s), str(mg.o), str(gd.o)],
                    "edge_iri": [str(mg.p), str(gd.p)],
                    "direction_of_edges": ["forward", "forward"],
                    "path_length": 2,
                    "interpretation_boundary": "STRUCTURAL_ONLY_NOT_RANK_CAUSALITY",
                }
            )

    ortholog_paths: list[dict[str, Any]] = []
    for _, mg in mouse_gene.iterrows():
        for _, og in orth[orth.s == mg.o].iterrows():
            for _, hd in human_gene_disease[human_gene_disease.s == og.o].iterrows():
                ortholog_paths.append(
                    {
                        "path_type": "MOUSE_GENE_HUMAN_ORTHOLOG_DISEASE_STRUCTURAL",
                        "path_nodes": [str(mg.s), str(mg.o), str(og.o), str(hd.o)],
                        "edge_iri": [str(mg.p), str(og.p), str(hd.p)],
                        "direction_of_edges": ["forward", "forward", "forward"],
                        "path_length": 3,
                        "interpretation_boundary": "STRUCTURAL_ONLY_NOT_RANK_CAUSALITY",
                    }
                )

    mouse_go = train[(train.s == mouse_iri) & (train.p.isin(GO_PREDICATES)) & (train.o.str.startswith(GO_PREFIX))].copy()
    train_go_keys = {
        (str(r.p), str(r.o)) for _, r in mouse_go.iterrows()
    }

    return {
        "mouse_gene_edges": _edge_records(mouse_gene, evidence_type="FROZEN_TRAIN_MOUSE_GENE", source_id="FROZEN_TRAIN"),
        "gene_disease_edges": _edge_records(gene_disease, evidence_type="FROZEN_TRAIN_GENE_DISEASE", source_id="FROZEN_TRAIN"),
        "orthology_edges": _edge_records(orth, evidence_type="FROZEN_TRAIN_ORTHOLOGY", source_id="FROZEN_TRAIN"),
        "human_gene_disease_edges": _edge_records(human_gene_disease, evidence_type="FROZEN_TRAIN_HUMAN_GENE_DISEASE", source_id="FROZEN_TRAIN"),
        "disease_hp_edges": _edge_records(disease_hp, evidence_type="FROZEN_TRAIN_DISEASE_HP", source_id="FROZEN_TRAIN"),
        "hp_mp_edges": _edge_records(hp_mp, evidence_type="FROZEN_TRAIN_HP_MP", source_id="FROZEN_TRAIN"),
        "mouse_mp_edges": _edge_records(mouse_mp, evidence_type="FROZEN_TRAIN_MOUSE_MP", source_id="FROZEN_TRAIN"),
        "mouse_go_edges": _edge_records(mouse_go, evidence_type="FROZEN_TRAIN_MOUSE_GO", source_id="FROZEN_TRAIN"),
        "direct_gene_paths": direct_gene_paths,
        "ortholog_gene_paths": ortholog_paths,
        "phenotype_paths": pheno_paths,
        "train_go_keys": train_go_keys,
    }


@lru_cache(maxsize=1)
def load_go_summary_verified() -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    source_meta = {name: _verified(path, sha) for name, (path, sha) in GO_FILES.items()}
    path = GO_FILES["go_evidence_summary"][0]
    expected_cols = [
        "mouse", "aspect", "predicate", "go_iri", "go_id", "routes",
        "uniprot_accessions", "ncbigene_iris", "evidence_codes", "references",
        "assigned_by", "gaf_relations", "matched_support_rows", "unmatched_support_rows",
    ]
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    if list(df.columns) != expected_cols:
        raise RuntimeError(f"GO summary header mismatch: {list(df.columns)!r}")
    bad_pred = set(df.predicate) - set(GO_PREDICATES)
    if bad_pred:
        raise RuntimeError(f"unexpected GO predicates in summary: {sorted(bad_pred)[:5]}")
    return df, source_meta


def go_evidence_for_mouse(mouse_iri: str, train_go_keys: set[tuple[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary, source_meta = load_go_summary_verified()
    x = summary[summary.mouse == mouse_iri].copy()
    term_counts = summary.groupby("go_iri", sort=False)["mouse"].nunique().to_dict()
    rows: list[dict[str, Any]] = []
    for _, r in x.iterrows():
        key = (str(r.predicate), str(r.go_iri))
        rows.append(
            {
                "mouse_iri": str(r.mouse),
                "aspect": str(r.aspect),
                "predicate_iri": str(r.predicate),
                "go_iri": str(r.go_iri),
                "source_routes": str(r.routes),
                "ncbigene_iris": str(r.ncbigene_iris),
                "evidence_codes": str(r.evidence_codes),
                "references": str(r.references),
                "assigned_by": str(r.assigned_by),
                "gaf_relations": str(r.gaf_relations),
                "matched_support_rows": str(r.matched_support_rows),
                "unmatched_support_rows": str(r.unmatched_support_rows),
                "mouse_count_for_go_term_in_summary": int(term_counts.get(str(r.go_iri), 0)),
                "in_frozen_train_mouse_go": key in train_go_keys,
                "interpretation_boundary": "GO_ASSOCIATION_NOT_AUTOMATIC_MECHANISTIC_SUPPORT",
            }
        )
    return rows, {
        "source_files": source_meta,
        "go_provenance_body_read": False,
        "go_support_bridge_body_read": False,
        "note": "V0.1 displays verified aggregate GO summary; row-level provenance/support bodies are not yet expanded in the UI.",
    }



def _gene_id_from_iri_or_text(value: str) -> str | None:
    """Extract a numeric NCBI Gene identifier from supported absolute-IRI text.

    This is identifier normalization for comparison only. Exported evidence keeps
    the original absolute IRIs/text unchanged.
    """
    import re
    text = str(value)
    m = re.search(r"(?:identifiers\.org/ncbigene/|ncbi\.nlm\.nih\.gov/gene/)(\d+)", text)
    return m.group(1) if m else None


def disease_gene_context_from_train(train: pd.DataFrame, disease_iri: str) -> dict[str, Any]:
    """Return source-native gene->disease edges and normalized gene IDs.

    No predicate is redefined here: rows are selected because the Frozen Train
    subject is an NCBI Gene absolute IRI and object is the queried disease IRI.
    """
    x = train[(train.o == disease_iri) & train.s.astype(str).str.contains('/ncbigene/', regex=False)].copy()
    gene_iris = sorted(set(x.s.astype(str)))
    gene_ids = sorted({g for g in (_gene_id_from_iri_or_text(v) for v in gene_iris) if g is not None}, key=int)
    return {
        "gene_disease_edges": _edge_records(
            x, evidence_type="FROZEN_TRAIN_DISEASE_GENE_CONTEXT", source_id="FROZEN_TRAIN"
        ),
        "gene_iris": gene_iris,
        "gene_ids": gene_ids,
    }


def derive_disease_gene_go_context(
    summary: pd.DataFrame,
    disease_gene_ids: list[str],
    candidate_go_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive disease-gene-linked GO context and exact overlap with a candidate Mouse.

    This is a post-hoc source intersection between:
      (a) genes linked to the disease in Frozen Train, and
      (b) GO summary rows whose aggregated ncbigene_iris contain those genes.

    It is NOT a Disease->GO assertion and NOT evidence that KGE causally used the
    matching GO term to assign the saved rank.
    """
    disease_gene_ids_set = {str(x) for x in disease_gene_ids}
    linked_rows: list[dict[str, Any]] = []
    term_counts = summary.groupby("go_iri", sort=False)["mouse"].nunique().to_dict()

    for idx, r in summary.iterrows():
        support_gene_ids = sorted({
            g for g in (_gene_id_from_iri_or_text(v) for v in str(r.ncbigene_iris).split("|"))
            if g is not None
        }, key=int)
        matched = sorted(disease_gene_ids_set & set(support_gene_ids), key=int)
        if not matched:
            continue
        linked_rows.append({
            "aspect": str(r.aspect),
            "predicate_iri": str(r.predicate),
            "go_iri": str(r.go_iri),
            "disease_gene_ids_matched": "|".join(matched),
            "source_routes": str(r.routes),
            "evidence_codes": str(r.evidence_codes),
            "references": str(r.references),
            "assigned_by": str(r.assigned_by),
            "mouse_count_for_go_term_in_summary": int(term_counts.get(str(r.go_iri), 0)),
            "go_summary_physical_row": int(idx) + 2,
            "interpretation_boundary": "DISEASE_GENE_LINKED_GO_CONTEXT_NOT_DISEASE_GO_ASSERTION",
        })

    # Deduplicate disease-side GO context by semantic term while retaining union of matched genes/routes/codes/refs.
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in linked_rows:
        key = (row["predicate_iri"], row["go_iri"])
        if key not in by_key:
            by_key[key] = dict(row)
            continue
        cur = by_key[key]
        for field in ("disease_gene_ids_matched", "source_routes", "evidence_codes", "references", "assigned_by"):
            vals = {v for v in str(cur.get(field, "")).split("|") if v}
            vals.update(v for v in str(row.get(field, "")).split("|") if v)
            cur[field] = "|".join(sorted(vals))
        cur["go_summary_physical_row"] = min(int(cur["go_summary_physical_row"]), int(row["go_summary_physical_row"]))

    disease_go = list(by_key.values())
    candidate_by_key = {(str(r["predicate_iri"]), str(r["go_iri"])): r for r in candidate_go_rows}
    shared: list[dict[str, Any]] = []
    for drow in disease_go:
        key = (drow["predicate_iri"], drow["go_iri"])
        crow = candidate_by_key.get(key)
        if crow is None:
            continue
        shared.append({
            "aspect": drow["aspect"],
            "predicate_iri": drow["predicate_iri"],
            "go_iri": drow["go_iri"],
            "disease_gene_ids_matched": drow["disease_gene_ids_matched"],
            "candidate_mouse_source_routes": str(crow.get("source_routes", "")),
            "candidate_mouse_evidence_codes": str(crow.get("evidence_codes", "")),
            "candidate_mouse_references": str(crow.get("references", "")),
            "disease_context_source_routes": drow["source_routes"],
            "disease_context_evidence_codes": drow["evidence_codes"],
            "disease_context_references": drow["references"],
            "mouse_count_for_go_term_in_summary": int(drow["mouse_count_for_go_term_in_summary"]),
            "interpretation_boundary": "EXACT_GO_SOURCE_INTERSECTION_POSTHOC_NOT_RANK_CAUSALITY",
        })

    shared.sort(key=lambda r: (r["aspect"], r["go_iri"]))
    disease_go.sort(key=lambda r: (r["aspect"], r["go_iri"]))
    return {
        "disease_gene_linked_go": disease_go,
        "shared_candidate_disease_gene_go": shared,
        "disease_gene_count": len(disease_gene_ids_set),
        "disease_gene_linked_go_count": len(disease_go),
        "candidate_go_count": len(candidate_go_rows),
        "shared_go_count": len(shared),
        "boundary": (
            "Disease-side GO is derived from Frozen-Train disease-linked genes intersected with pinned GO summary support. "
            "It is not a direct Disease->GO assertion and does not establish KGE rank causality."
        ),
    }

def _walk_json_like(x: Any, visit) -> None:
    if isinstance(x, dict):
        visit(x)
        for v in x.values():
            _walk_json_like(v, visit)
    elif isinstance(x, list):
        for v in x:
            _walk_json_like(v, visit)
    elif isinstance(x, str) and x.startswith("{"):
        try:
            _walk_json_like(json.loads(x), visit)
        except Exception:
            pass


def extract_historical_group_core(obj: dict[str, Any], rbrc_id: str) -> dict[str, Any]:
    """Extract only the reusable group-level core for one RBRC ID.

    This deliberately ignores candidate-specific LLM assessments for the selected
    RBRC-GSC0032. A record for another Mouse only establishes membership in the
    historical matched-Mouse group and the group-level GCK/MGI/MedGen context.
    """
    gene_rows: list[dict[str, Any]] = []
    mouse_rows: list[dict[str, Any]] = []
    mapped_diseases_variants: set[str] = set()

    def visit(x: dict[str, Any]) -> None:
        mids = x.get("matched_mouse_ids")
        if isinstance(mids, list) and rbrc_id in mids:
            gene_rows.append({
                "gene_symbol": x.get("gene_symbol"),
                "human_gene_id": x.get("human_gene_id"),
                "gene_id_iri": x.get("gene_id_iri"),
                "sources": x.get("sources"),
                "matched_mouse_count": x.get("matched_mouse_count"),
            })
        if x.get("strain_id") == rbrc_id:
            mouse_rows.append({
                "strain_id": x.get("strain_id"),
                "strain_name": x.get("strain_name"),
                "sources": x.get("sources"),
                "mapped_disease": x.get("mapped_disease"),
            })
            mapped_diseases_variants.add(json.dumps(x.get("mapped_diseases"), ensure_ascii=False, sort_keys=True))

    _walk_json_like(obj, visit)

    def unique(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in rows:
            key = json.dumps(r, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    return {
        "gene_contexts": unique(gene_rows),
        "mouse_records": unique(mouse_rows),
        "mapped_diseases_schema_variants": sorted(mapped_diseases_variants),
    }


@lru_cache(maxsize=64)
def historical_sparql_llm_consensus(disease_iri: str, rbrc_id: str) -> dict[str, Any]:
    if disease_iri != HISTORICAL_BOUND_DISEASE_IRI:
        return {
            "status": "OUT_OF_BOUND_SCOPE",
            "evidence_scope": "NONE",
            "candidate_specific_claim": False,
            "records": [],
            "boundary": "The pinned historical consensus set is specific to MONDO_0005148.",
        }

    file_meta: list[dict[str, Any]] = []
    per_file: list[dict[str, Any]] = []
    for path, expected_sha in HISTORICAL_SPARQL_LLM_FILES:
        meta = _verified(path, expected_sha)
        obj = json.loads(path.read_text(encoding="utf-8"))
        core = extract_historical_group_core(obj, rbrc_id)
        file_meta.append(meta)
        per_file.append(core)

    presence = [bool(x["mouse_records"] and x["gene_contexts"]) for x in per_file]
    if not any(presence):
        return {
            "status": "NO_GROUP_MATCH",
            "evidence_scope": "NONE",
            "candidate_specific_claim": False,
            "source_files": file_meta,
            "records": [],
            "boundary": "Candidate is not present in the matched-Mouse group of the pinned historical outputs.",
        }
    if not all(presence):
        raise RuntimeError(f"historical SPARQL+LLM presence disagreement across pinned files: {presence}")

    gene_keys = {
        json.dumps(x["gene_contexts"], ensure_ascii=False, sort_keys=True)
        for x in per_file
    }
    mouse_keys = {
        json.dumps(x["mouse_records"], ensure_ascii=False, sort_keys=True)
        for x in per_file
    }
    if len(gene_keys) != 1 or len(mouse_keys) != 1:
        raise RuntimeError("historical SPARQL+LLM core evidence disagreement across 7 pinned files")

    gene_context = per_file[0]["gene_contexts"]
    mouse_record = per_file[0]["mouse_records"]
    if len(gene_context) != 1 or len(mouse_record) != 1:
        raise RuntimeError("historical SPARQL+LLM normalized core is not unique")

    schema_variants = sorted({v for x in per_file for v in x["mapped_diseases_schema_variants"]})
    return {
        "status": "CONSENSUS_7_OF_7",
        "evidence_scope": "HISTORICAL_GROUP_LEVEL_MATCH",
        "candidate_specific_claim": False,
        "consensus_file_count": len(per_file),
        "group_gene_context": gene_context[0],
        "matched_mouse_record": mouse_record[0],
        "mapped_diseases_schema_variants": schema_variants,
        "source_files": file_meta,
        "scientific_boundary": (
            "This proves only that the candidate was repeatedly stored in the historical matched-Mouse group under the "
            "GCK/MGI/MedGen context for MONDO_0005148. It does not prove candidate-specific allele identity, phenotype "
            "reproduction, primary-literature support, model validity, or causal contribution to the KGE rank."
        ),
    }


def candidate_specific_external_evidence(disease_iri: str, rbrc_id: str) -> dict[str, Any]:
    if disease_iri != CANDIDATE_SNAPSHOT_DISEASE_IRI or rbrc_id != CANDIDATE_SNAPSHOT_RBRC_ID:
        return {
            "status": "NOT_ASSESSED_FOR_THIS_CANDIDATE_V0_6",
            "candidate_specific_claim": False,
            "boundary": "V0.6 binds candidate-specific external evidence only for MONDO_0005148 x RBRC-GSC0231.",
        }
    # FIX5: verify exactly the bytes consumed; a cached prior SHA is not accepted.
    # The original snapshot remains read-only and outside the candidate checkout.
    snapshot_bytes = CANDIDATE_SNAPSHOT_PATH.read_bytes()
    observed_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    if observed_sha256 != CANDIDATE_SNAPSHOT_EXPECTED_SHA256:
        raise RuntimeError(
            "candidate-specific snapshot SHA256 mismatch: "
            f"{CANDIDATE_SNAPSHOT_PATH} observed={observed_sha256} "
            f"expected={CANDIDATE_SNAPSHOT_EXPECTED_SHA256}"
        )
    meta = {
        "path": str(CANDIDATE_SNAPSHOT_PATH),
        "sha256": observed_sha256,
        "size_bytes": len(snapshot_bytes),
    }
    obj = json.loads(snapshot_bytes)
    if obj.get("disease_scope") != disease_iri:
        raise RuntimeError("candidate-specific snapshot disease identity mismatch")
    cand = obj.get("candidate", {})
    if cand.get("rbrc_id") != rbrc_id:
        raise RuntimeError("candidate-specific snapshot RBRC identity mismatch")
    if obj.get("scientific_boundary", {}).get("candidate_specific_primary_experimental_paper") != "NOT_IDENTIFIED_AFTER_PROJECT_CHAT_AND_EXTERNAL_SOURCE_REVIEW":
        raise RuntimeError("unexpected primary-literature status in V0.6 snapshot")
    return {
        "status": "CANDIDATE_SPECIFIC_EXTERNAL_SNAPSHOT_BOUND",
        "candidate_specific_claim": True,
        "snapshot_meta": meta,
        "catalog": obj.get("catalog", {}),
        "mgi_allele": obj.get("mgi_allele", {}),
        "mgi_phenotype": obj.get("mgi_phenotype", {}),
        "references": obj.get("references", []),
        "scientific_boundary": obj.get("scientific_boundary", {}),
        "snapshot_status": obj.get("snapshot_status"),
        "observed_on": obj.get("observed_on"),
    }



def derive_provisional_assessment(candidate_external: dict[str, Any]) -> dict[str, Any]:
    """Derive a bounded, deterministic proposal from candidate-specific evidence only.

    This is not an expert review and not an LLM result. KGE rank, GO overlap,
    historical group membership, and citation count are deliberately excluded.
    """
    out = {
        "ruleset_id": PROVISIONAL_ASSESSMENT_RULESET_ID,
        "status": "NOT_ASSESSED",
        "generated_by": "DETERMINISTIC_EVIDENCE_RULESET_NOT_LLM",
        "expert_review_required": True,
        "proposed_f_class": "Not assessed",
        "proposed_hml": "Not assessed",
        "stock_phenotype": "NOT_ASSESSED",
        "disease_model_validity": "NOT_ASSESSED",
        "source_independence": "NOT_ESTABLISHED",
        "kge_rank_causality": "NOT_ESTABLISHED",
        "evidence_basis": [],
        "exclusions": [
            "KGE rank is not used to assign F1-F4 or H/M/L.",
            "GO overlap, GO frequency/IDF, and citation count are not used to assign F1-F4 or H/M/L.",
            "Historical SPARQL+LLM group membership is not treated as candidate-specific phenotype or publication evidence.",
        ],
    }
    if candidate_external.get("status") != "CANDIDATE_SPECIFIC_EXTERNAL_SNAPSHOT_BOUND":
        return out

    boundary = candidate_external.get("scientific_boundary") or {}
    allele = candidate_external.get("mgi_allele") or {}
    phenotype = candidate_external.get("mgi_phenotype") or {}

    checks = {
        "candidate_specific_allele_identity": boundary.get("candidate_specific_allele_identity") == "SUPPORTED",
        "candidate_specific_hyperglycemia": boundary.get("candidate_specific_hyperglycemia") == "SUPPORTED_BY_MGI_PHENOTYPE_ANNOTATION",
        "phenotype_exact": phenotype.get("phenotype") == "hyperglycemia",
        "blood_glucose_observed": phenotype.get("blood_glucose_11_weeks_mg_dl") == 254,
        "primary_experimental_paper_absent": boundary.get("candidate_specific_primary_experimental_paper") == "NOT_IDENTIFIED_AFTER_PROJECT_CHAT_AND_EXTERNAL_SOURCE_REVIEW",
        "t2d_validity_not_established": boundary.get("t2d_model_validity") == "NOT_ESTABLISHED_BY_THESE_SOURCES_ALONE",
        "rank_causality_not_established": boundary.get("kge_rank_causality") == "NOT_ESTABLISHED",
    }
    if not all(checks.values()):
        out["evidence_checks"] = checks
        return out

    out.update({
        "status": "PROVISIONAL_RULE_BASED_NOT_EXPERT_REVIEWED",
        "proposed_f_class": "F3",
        "proposed_hml": "Medium",
        "stock_phenotype": "CANDIDATE_SPECIFIC_HYPERGLYCEMIA_SUPPORTED_NOT_T2D_REPRODUCTION",
        "disease_model_validity": "NOT_ESTABLISHED",
        "source_independence": "NOT_ESTABLISHED",
        "kge_rank_causality": "NOT_ESTABLISHED",
        "evidence_checks": checks,
        "evidence_basis": [
            {
                "claim": "candidate-specific allele identity",
                "status": "SUPPORTED",
                "identifier": allele.get("mgi_allele_id"),
                "allele": allele.get("allele_symbol"),
                "mutation": allele.get("mutation_description"),
            },
            {
                "claim": "candidate-specific hyperglycemia observation",
                "status": "SUPPORTED_BY_MGI_PHENOTYPE_ANNOTATION",
                "phenotype": phenotype.get("phenotype"),
                "blood_glucose_11_weeks_mg_dl": phenotype.get("blood_glucose_11_weeks_mg_dl"),
                "reference": phenotype.get("phenotype_reference"),
            },
            {
                "claim": "candidate-specific peer-reviewed primary experimental paper",
                "status": "NOT_IDENTIFIED",
            },
            {
                "claim": "T2D model validity",
                "status": "NOT_ESTABLISHED_BY_THESE_SOURCES_ALONE",
            },
        ],
        "rationale": [
            "F3 is proposed because candidate-specific phenotype observation/resource evidence exists, while a candidate-specific peer-reviewed primary experimental paper was not identified.",
            "Medium is proposed because the exact candidate allele has a disease-direction-consistent hyperglycemia annotation, but full T2D model validity and candidate-specific primary experimental literature remain unestablished.",
        ],
    })
    return out


def validate_provisional_assessment(provisional: dict[str, Any]) -> None:
    if provisional.get("status") not in PROVISIONAL_STATUS_ALLOWED:
        raise RuntimeError("invalid provisional assessment status")
    if provisional.get("proposed_f_class") not in F_ALLOWED:
        raise RuntimeError("invalid provisional F1-F4 proposal")
    if provisional.get("proposed_hml") not in HML_ALLOWED:
        raise RuntimeError("invalid provisional H/M/L proposal")
    if provisional.get("generated_by") != "DETERMINISTIC_EVIDENCE_RULESET_NOT_LLM":
        raise RuntimeError("unexpected provisional assessment generator")

def validate_assessment(assessment: dict[str, Any]) -> None:
    if assessment.get("f_class") not in F_ALLOWED:
        raise RuntimeError("invalid F1-F4 assessment")
    if assessment.get("hml") not in HML_ALLOWED:
        raise RuntimeError("invalid H/M/L assessment")
    if assessment.get("review_status") not in REVIEW_ALLOWED:
        raise RuntimeError("invalid review_status")
    if assessment.get("hml") == "Not assessed" and assessment.get("review_status") == "expert_reviewed":
        raise RuntimeError("Not assessed cannot be presented as expert-reviewed assessment result")


def build_evidence_bundle(
    *,
    disease_iri: str,
    mouse_iri: str,
    ranking: dict[str, Any],
    ranking_verification_receipt: dict[str, Any],
) -> dict[str, Any]:
    # FIX6 F06: no caller-provided frozen_flag; independent rank-row contract
    # must originate from the SHA-pinned official 8504 helper loader.
    # Receipt binds the selected disease, Mouse, family, rank and family SHA.
    verified_ranking = validate_receipt(
        receipt=ranking_verification_receipt,
        disease_iri=disease_iri,
        mouse_iri=mouse_iri,
        ranking=ranking,
    )
    train, train_meta = load_frozen_train()
    structural = derive_train_evidence(train, disease_iri, mouse_iri)
    go_rows, go_meta = go_evidence_for_mouse(mouse_iri, structural["train_go_keys"])
    disease_gene_context = disease_gene_context_from_train(train, disease_iri)
    go_summary, _ = load_go_summary_verified()
    go_context = derive_disease_gene_go_context(go_summary, disease_gene_context["gene_ids"], go_rows)
    rbrc_id = mouse_iri.rstrip("/").rsplit("/", 1)[-1]
    historical = historical_sparql_llm_consensus(disease_iri, rbrc_id)
    candidate_external = candidate_specific_external_evidence(disease_iri, rbrc_id)

    provisional = derive_provisional_assessment(candidate_external)
    validate_provisional_assessment(provisional)
    assessment = {
        "f_class": "Not assessed",
        "hml": "Not assessed",
        "stock_phenotype": provisional.get("stock_phenotype", "NOT_ASSESSED"),
        "source_independence": provisional.get("source_independence", "NOT_ESTABLISHED"),
        "review_status": "unreviewed",
        "llm_provisional_status": "NOT_RUN_V0_6",
        "provisional_assessment": provisional,
        "formal_assessment_boundary": {
            "f_class": "Not assessed",
            "hml": "Not assessed",
            "review_status": "unreviewed",
            "formal_state_mutated": False,
        },
        "rules": [
            "F1 does not imply High; F4 does not imply Low.",
            "Not assessed is distinct from Low.",
            "KGE rank, GO exact match, GO frequency/IDF, literature count, and historical group membership do not assign H/M/L or F1-F4.",
            "Stock phenotype reproduction is a separate variable from mechanistic H/M/L.",
            "The V0.6 F3/Medium proposal is provisional, deterministic, not LLM-generated, and not expert-reviewed.",
        ],
    }
    validate_assessment(assessment)

    source_edges = {
        "candidate_intrinsic": (
            structural["mouse_gene_edges"]
            + structural["mouse_mp_edges"]
            + structural["mouse_go_edges"]
        ),
        "candidate_linking": (
            structural["gene_disease_edges"]
            + structural["orthology_edges"]
            + structural["human_gene_disease_edges"]
            + structural["hp_mp_edges"]
        ),
        "disease_context": (
            disease_gene_context["gene_disease_edges"]
            + structural["disease_hp_edges"]
        ),
    }
    indirect_paths = (
        structural["direct_gene_paths"]
        + structural["ortholog_gene_paths"]
        + structural["phenotype_paths"]
    )

    bundle = {
        "schema_id": SCHEMA_ID,
        "implementation_status": IMPLEMENTATION_STATUS,
        "identity": {
            "disease_iri": disease_iri,
            "mouse_iri": mouse_iri,
            "rbrc_id": rbrc_id,
            "retrieval_source": "KGE_8504_ISOLATED_EVIDENCE_ADAPTER",
        },
        "ranking": {**ranking, "frozen_flag": verified_ranking["status"] == "OFFICIAL_8504_PINNED_LOADER_SELECTED_ROW_VERIFIED"},
        "source_edges": source_edges,
        "structural_paths": indirect_paths,
        "go_context": {
            "candidate_mouse_go": go_rows,
            **go_context,
        },
        "historical_sparql_llm_evidence": historical,
        "strain_and_allele": {
            "status": candidate_external.get("status"),
            "catalog_snapshot": candidate_external.get("catalog"),
            "allele_identity": candidate_external.get("mgi_allele"),
            "genetic_background": (candidate_external.get("mgi_phenotype") or {}).get("genetic_background"),
            "phenotype": candidate_external.get("mgi_phenotype"),
            "candidate_specific_claim": candidate_external.get("candidate_specific_claim", False),
            "snapshot_meta": candidate_external.get("snapshot_meta"),
            "boundary": (candidate_external.get("scientific_boundary") or {}),
        },
        "external_papers": {
            "status": candidate_external.get("status"),
            "records": candidate_external.get("references", []),
            "primary_experimental_paper_status": (candidate_external.get("scientific_boundary") or {}).get("candidate_specific_primary_experimental_paper", "NOT_ASSESSED"),
            "boundary": "Aigner 2008 is treated as a review article; J:133634 is a web resource. Neither is promoted to a candidate-specific primary experimental paper.",
        },
        "assessment": assessment,
        "unproven_scope": [
            "Structural paths do not prove that KGE used that path causally to assign the saved rank.",
            "GO association does not by itself establish disease mechanism or model validity.",
            "No claim is made that the distributed RBRC stock reproduces the target disease phenotype.",
            "Historical SPARQL+LLM group membership is not candidate-specific strain/allele/catalog/publication evidence.",
            "Candidate-specific strain/allele/catalog/phenotype evidence is bound only for the explicitly pinned RBRC-GSC0231 snapshot; other candidates remain unassessed.",
            "No candidate-specific peer-reviewed primary experimental paper was identified after project-chat review and external-source review for RBRC-GSC0231.",
            "Disease-gene-linked GO overlap is post-hoc structural context, not a direct Disease->GO assertion or a causal explanation of rank.",
        ],
        "provenance": {
            "ranking_verification": verified_ranking,
            "frozen_train": train_meta,
            "go": go_meta,
            "primary_test_access": False,
            "test_access": False,
            "withheld_access": False,
            "training": False,
            "validation_rescoring": False,
            "ranking_mutation": False,
            "network_retrieval": False,
            "llm_call": False,
        },
    }
    # train_go_keys is an internal derivation helper and must not leak as a set in JSON.
    json.dumps(bundle, ensure_ascii=False)
    return bundle


def llm_input_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    """Produce a bounded, source-backed payload for a future provisional LLM step.

    No model call is performed here. The payload intentionally keeps Not assessed
    fields and all unproven-scope statements.
    """
    return {
        "task": "Provisional biological interpretation only; do not alter ranking or claim expert review.",
        "constraints": [
            "Use only identifiers and evidence present in this payload.",
            "Do not invent PMID/DOI/IRI/allele/phenotype facts.",
            "Do not infer High/Medium/Low from KGE rank, GO match, term frequency, or citation count alone.",
            "Keep Not assessed distinct from Low.",
            "Separate observed evidence, inference, contradiction, and missing evidence.",
            "Return provisional status only.",
            "Do not overwrite the formal Not assessed / unreviewed state or present the deterministic V0.6 proposal as expert review.",
        ],
        "evidence_bundle": bundle,
    }

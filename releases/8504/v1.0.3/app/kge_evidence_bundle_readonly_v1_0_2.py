#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""8504 v1.0.2 Emergency scope-corrected read-only evidence adapter.

Frozen Train and GO evidence remain available for any selected disease/candidate.
Old single-disease SPARQL+LLM files and single-mouse external snapshot are not
loaded, inferred, or presented as generic evidence. All unavailable comparison
features are explicitly NOT_CONNECTED, never NEGATIVE or NO_MATCH.
No network access, LLM calls, retraining or rank mutation.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import stat
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from kge_verified_ranking_contract_v0_1 import (
    assert_live_ranking_authority, bind_live_evidence_bundle, validate_receipt,
    InProcessRankingAuthority,
)

SCHEMA_ID = "KGE_MOUSE_EVIDENCE_BUNDLE_SCOPE_CORRECTED_V1_0_2_20261028"
IMPLEMENTATION_STATUS = "MAC_LOCAL_EMERGENCY_SCOPE_CORRECTION_V1_0_2_UNDER_REVIEW"

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


def _source_signature(path: Path) -> tuple[int, int, int, int, int]:
    """Fast *local identity/freshness* marker; not a cryptographic digest.

    ctime_ns catches same-size edits with restored mtime on normal filesystems;
    inode catches an atomic replacement. Exact SHA is checked on first visit or
    whenever this signature changes. Filesystem adversaries outside these
    assumptions require immutable snapshots or full re-hash on every access.
    """
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"evidence source is not a regular file: {path}")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_verified_source(path: Path, expected_sha256: str, signature: tuple[int, ...], *, keep_bytes: bool) -> tuple[dict[str, Any], bytes | None]:
    """Read exactly one file descriptor, SHA-check it, and check identity again."""
    path = Path(path)
    if _source_signature(path) != signature:
        raise RuntimeError("evidence source changed before verification")
    h = hashlib.sha256()
    chunks = [] if keep_bytes else None
    length = 0
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        opened_sig = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        if opened_sig != signature:
            raise RuntimeError("evidence source replaced during open")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
            length += len(chunk)
            if keep_bytes:
                chunks.append(chunk)
        ending = os.fstat(stream.fileno())
        ending_sig = (ending.st_dev, ending.st_ino, ending.st_size, ending.st_mtime_ns, ending.st_ctime_ns)
        if ending_sig != signature:
            raise RuntimeError("evidence source changed while being read")
    if _source_signature(path) != signature or length != signature[2]:
        raise RuntimeError("evidence source changed after verification")
    observed = h.hexdigest()
    if observed != expected_sha256:
        raise RuntimeError(
            f"evidence source SHA256 mismatch: {path} observed={observed} expected={expected_sha256}"
        )
    return {
        "path": str(path), "sha256": observed, "size_bytes": length,
        "verification_method": "EXACT_SHA256_ON_FIRST_OR_CHANGED_IDENTITY_STAT_CHECK_ON_CACHE_HIT",
    }, (b"".join(chunks) if keep_bytes else None)


@lru_cache(maxsize=32)
def _verify_file_cached(path_str: str, expected_sha256: str, signature: tuple[int, ...]) -> dict[str, Any]:
    meta, _ = _read_verified_source(Path(path_str), expected_sha256, signature, keep_bytes=False)
    return meta


def _verified(path: Path, expected_sha256: str) -> dict[str, Any]:
    path = Path(path)
    signature = _source_signature(path)
    meta = _verify_file_cached(str(path), expected_sha256, signature)
    if _source_signature(path) != signature:
        raise RuntimeError("evidence source changed during cached identity check")
    return dict(meta)


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
def _parsed_train_cached(path_str: str, expected_sha256: str, signature: tuple[int, ...]) -> pd.DataFrame:
    # A single byte sequence must be SHA-verified and parsed, not separate
    # hash(path) + pandas.read_csv(path) calls vulnerable to intervening edits.
    _, data = _read_verified_source(Path(path_str), expected_sha256, signature, keep_bytes=True)
    df = pd.read_csv(
        io.BytesIO(data), sep="\t", header=None,
        names=["s", "p", "o"], dtype=str, keep_default_na=False,
    )
    if list(df.columns) != ["s", "p", "o"] or len(df) == 0:
        raise RuntimeError("Frozen Train schema/read failure")
    if (df == "").any().any():
        raise RuntimeError("Frozen Train contains blank s/p/o in candidate reader")
    return df


def load_frozen_train() -> tuple[pd.DataFrame, dict[str, Any]]:
    path, meta = resolve_frozen_train()
    signature = _source_signature(path)
    df = _parsed_train_cached(str(path), TRAIN_EXPECTED_SHA256, signature)
    if _source_signature(path) != signature:
        raise RuntimeError("Frozen Train source changed after parser cache selection")
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
def _parsed_go_summary_cached(path_str: str, expected_sha256: str, signature: tuple[int, ...]) -> pd.DataFrame:
    _, data = _read_verified_source(Path(path_str), expected_sha256, signature, keep_bytes=True)
    expected_cols = [
        "mouse", "aspect", "predicate", "go_iri", "go_id", "routes",
        "uniprot_accessions", "ncbigene_iris", "evidence_codes", "references",
        "assigned_by", "gaf_relations", "matched_support_rows", "unmatched_support_rows",
    ]
    df = pd.read_csv(io.BytesIO(data), sep="\t", dtype=str, keep_default_na=False)
    if list(df.columns) != expected_cols:
        raise RuntimeError(f"GO summary header mismatch: {list(df.columns)!r}")
    bad_pred = set(df.predicate) - set(GO_PREDICATES)
    if bad_pred:
        raise RuntimeError(f"unexpected GO predicates in summary: {sorted(bad_pred)[:5]}")
    return df


def load_go_summary_verified() -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    # Every access checks on-disk source identity; unchanged pinned sources
    # reuse the verified immutable dataframe; a modified source is rehashed.
    source_meta = {name: _verified(path, sha) for name, (path, sha) in GO_FILES.items()}
    path, expected = GO_FILES["go_evidence_summary"]
    signature = _source_signature(path)
    df = _parsed_go_summary_cached(str(path), expected, signature)
    if _source_signature(path) != signature:
        raise RuntimeError("GO summary source changed after parser cache selection")
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

def historical_sparql_llm_consensus(disease_iri: str, rbrc_id: str) -> dict[str, Any]:
    """Fail-safe scope statement; no historical output is loaded for any disease.

    The only historical records supplied with v1.0.1 were from one disease.
    We cannot honestly describe these as an equal-scope comparison for arbitrary
    selected disease/candidate pairs, even if the pair happens to be that case.
    """
    return {
        "status": "NOT_CONNECTED_EQUAL_SCOPE_SPARQL_LLM",
        "evidence_scope": "NO_CURRENT_COMPARISON_LOADED",
        "candidate_specific_claim": False,
        "selected_disease_iri": disease_iri,
        "selected_rbrc_id": rbrc_id,
        "records": [],
        "boundary": (
            "No selected-disease / selected-mouse equivalent-source SPARQL+LLM "
            "record is loaded in v1.0.2. This is NOT a negative search result. "
            "Historic single-disease files are excluded from this generic panel."
        ),
    }


def candidate_specific_external_evidence(disease_iri: str, rbrc_id: str) -> dict[str, Any]:
    """Do not reinterpret archived single-pair snapshots as universal evidence."""
    return {
        "status": "NOT_CONNECTED_CANDIDATE_SPECIFIC_SOURCES",
        "candidate_specific_claim": False,
        "selected_disease_iri": disease_iri,
        "selected_rbrc_id": rbrc_id,
        "boundary": (
            "No candidate-specific external evidence is loaded in the emergency "
            "scope-corrected release. NOT ASSESSED is not a negative biological finding."
        ),
    }


def derive_provisional_assessment(candidate_external: dict[str, Any]) -> dict[str, Any]:
    """Conservative generic default; no single-case phenotype / F3/HML rule."""
    return {
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
            "KGE ranks and GO overlaps are not sufficient for disease-model assessment.",
            "Case-specific external evidence is NOT CONNECTED for this release.",
            "Official F/HML remains Not assessed until independent scientific review.",
        ],
    }


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
    trusted_ranking_authority: InProcessRankingAuthority,
) -> dict[str, Any]:
    # FIX8 R03: an unsigned JSON receipt is an integrity checksum, NOT authority.
    # The live, non-serializable context must come from the pinned loader frame.
    assert_live_ranking_authority(
        authority=trusted_ranking_authority, disease_iri=disease_iri,
        mouse_iri=mouse_iri, ranking=ranking,
        receipt=ranking_verification_receipt,
    )
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
            "No positive provisional F/HML is proposed without verified candidate-specific evidence.",
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
            "boundary": "Candidate-specific literature sources are NOT CONNECTED in v1.0.2; no negative or positive paper claim is made.",
        },
        "assessment": assessment,
        "unproven_scope": [
            "Structural paths do not prove that KGE used that path causally to assign the saved rank.",
            "GO association does not by itself establish disease mechanism or model validity.",
            "No claim is made that the distributed RBRC stock reproduces the target disease phenotype.",
            "Current-disease current-mouse SPARQL+LLM comparison is NOT CONNECTED; no negative search finding is claimed.",
            "Case-specific strain/allele/catalog/phenotype external sources are NOT CONNECTED for any candidate in v1.0.2; all remain unassessed.",
            "No candidate-specific primary-paper lookup is performed; NOT ASSESSED does not mean absent.",
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
    # Bind the entire newly generated JSON-compatible Evidence Bundle to the
    # current verified-loader context. Uploaded JSON never carries this context.
    bind_live_evidence_bundle(authority=trusted_ranking_authority, bundle=bundle)
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

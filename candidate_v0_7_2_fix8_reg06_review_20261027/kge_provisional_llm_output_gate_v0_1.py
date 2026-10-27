#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F04 FIX7 conservative identity + provenance screening gate (no LLM call).

The fixed Draft 2020-12 schema checks syntax/structure. This additional gate
checks output identity against the exact Evidence Bundle request and citations
against explicit source fields in the verified input. A passing check only
means identity and identifier *membership* match: it cannot prove that a cited
record entails a biological claim, nor that the LLM explanation is accurate.
Therefore unreviewed positive scientific judgments are held, not certified.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from kge_verified_ranking_contract_v0_1 import (
    assert_live_evidence_bundle, InProcessRankingAuthority, RankingProvenanceError,
)

GATE_ID = "KGE_8504_F04_LLM_OUTPUT_SOURCE_BOUNDARY_V0_2_CONSERVATIVE"
SCHEMA_SHA256 = "a1f88e3036463a356b8101008fedb900adbc108aa247bb5544cd5a7070449c90"
MAX_CLAIMS = 100
MAX_EVIDENCE_IDENTIFIERS_PER_CLAIM = 64
MAX_IDENTIFIER_LENGTH = 2048
SUPPORTED_STATUSES = frozenset(("SUPPORTED", "PARTIAL", "CONTRADICTED"))
_EXCLUDE = {"", "none", "null", "na", "n/a", "not assessed", "unreviewed", "not identified", "unknown", "-"}
_RE_FIELD = re.compile(r"(?:^|_)(?:iri|iris|reference|references|identifier|reference_id|source_url|pmid|doi|mgi_allele_id|gene_mgi_id)$", re.I)


class OutputEvidenceContractError(ValueError):
    """The provisional result is structurally or provenance-inconsistent."""


def _add(allow: set[str], obj: Any) -> None:
    if not isinstance(obj, str):
        return
    for token in re.split(r"\s*[|;]\s*", obj):
        val = token.strip()
        if 0 < len(val) <= MAX_IDENTIFIER_LENGTH and val.lower() not in _EXCLUDE:
            allow.add(val)


def collect_evidence_identifiers(bundle: Mapping[str, Any]) -> frozenset[str]:
    """Only original provenance-bearing fields, never arbitrary free text."""
    found: set[str] = set()
    edges = bundle.get("source_edges")
    if isinstance(edges, dict):
        for group in ("candidate_intrinsic", "candidate_linking", "disease_context"):
            for edge in edges.get(group, []):
                if not isinstance(edge, dict):
                    continue
                for key in ("subject_iri", "predicate_iri", "object_iri"):
                    _add(found, edge.get(key))
                row, src = edge.get("source_row_number"), edge.get("source_id")
                if type(row) is int and row > 0 and src == "FROZEN_TRAIN":
                    found.add(f"FROZEN_TRAIN:ROW:{row}")
    go = bundle.get("go_context")
    if isinstance(go, dict):
        for group in ("candidate_mouse_go", "disease_gene_linked_go", "shared_candidate_disease_gene_go"):
            for record in go.get(group, []):
                if not isinstance(record, dict):
                    continue
                for key, val in record.items():
                    if _RE_FIELD.search(str(key)) and isinstance(val, str):
                        _add(found, val)
    strain = bundle.get("strain_and_allele")
    if isinstance(strain, dict):
        fields = {
            "catalog_snapshot": ("source_url", "gene_mgi_id", "allele_symbol"),
            "allele_identity": ("source_url", "mgi_allele_id", "allele_symbol", "mutation_reference"),
            "phenotype": ("source_url", "phenotype_reference", "allelic_composition"),
        }
        for key, allowed_keys in fields.items():
            record = strain.get(key)
            if isinstance(record, dict):
                for k in allowed_keys:
                    _add(found, record.get(k))
    papers = bundle.get("external_papers")
    if isinstance(papers, dict):
        for record in papers.get("records", []):
            if isinstance(record, dict):
                for k in ("reference_id", "pmid", "doi", "source_url", "url", "publication_id"):
                    _add(found, record.get(k))
    # Group-level historical evidence is NOT candidate-specific evidence. It may
    # be cited by its own gene IRI only; this function does not promote it to
    # candidate-specific phenotype or primary-paper evidence.
    historical = bundle.get("historical_sparql_llm_evidence")
    if isinstance(historical, dict):
        if historical.get("status") == "CONSENSUS_7_OF_7":
            gene = historical.get("group_gene_context")
            if isinstance(gene, dict):
                _add(found, gene.get("gene_id_iri"))
    return frozenset(found)


# IMPORTANT: This is not a biological entailment checker. These origin tags
# prevent mistaking a GO/frozen-graph/historical mention for primary experimental
# evidence. They are never sufficient to authorize a positive scientific claim.
SOURCE_SCOPE_GRAPH = "FROZEN_TRAIN_GRAPH_CONTEXT"
SOURCE_SCOPE_GO = "GO_SUMMARY_OR_POSTHOC_CONTEXT"
SOURCE_SCOPE_CURATED = "CANDIDATE_SPECIFIC_CURATED_SNAPSHOT"
SOURCE_SCOPE_EXTERNAL = "EXTERNAL_REFERENCE_UNREVIEWED"
SOURCE_SCOPE_HISTORICAL = "HISTORICAL_GROUP_CONTEXT"


def collect_typed_evidence_identifiers(bundle: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Return source-origin categories, not claim-to-source entailment."""
    scopes: dict[str, set[str]] = {
        SOURCE_SCOPE_GRAPH: set(), SOURCE_SCOPE_GO: set(),
        SOURCE_SCOPE_CURATED: set(), SOURCE_SCOPE_EXTERNAL: set(),
        SOURCE_SCOPE_HISTORICAL: set(),
    }
    edges = bundle.get("source_edges") or {}
    if isinstance(edges, dict):
        for group in ("candidate_intrinsic", "candidate_linking", "disease_context"):
            for e in edges.get(group, []):
                if isinstance(e, dict):
                    for key in ("subject_iri", "predicate_iri", "object_iri"):
                        _add(scopes[SOURCE_SCOPE_GRAPH], e.get(key))
                    if e.get("source_id") == "FROZEN_TRAIN" and type(e.get("source_row_number")) is int and e["source_row_number"] > 0:
                        scopes[SOURCE_SCOPE_GRAPH].add(f"FROZEN_TRAIN:ROW:{e['source_row_number']}")
    go = bundle.get("go_context") or {}
    if isinstance(go, dict):
        for group in ("candidate_mouse_go", "disease_gene_linked_go", "shared_candidate_disease_gene_go"):
            for rec in go.get(group, []):
                if isinstance(rec, dict):
                    for key, val in rec.items():
                        if _RE_FIELD.search(str(key)):
                            _add(scopes[SOURCE_SCOPE_GO], val)
    cand = bundle.get("strain_and_allele") or {}
    if isinstance(cand, dict) and cand.get("candidate_specific_claim") is True:
        for subkey, fields in {
            "catalog_snapshot": ("source_url", "gene_mgi_id", "allele_symbol"),
            "allele_identity": ("source_url", "mgi_allele_id", "allele_symbol", "mutation_reference"),
            "phenotype": ("source_url", "phenotype_reference", "allelic_composition"),
        }.items():
            rec = cand.get(subkey)
            if isinstance(rec, dict):
                for field in fields:
                    _add(scopes[SOURCE_SCOPE_CURATED], rec.get(field))
    papers = bundle.get("external_papers") or {}
    if isinstance(papers, dict):
        for rec in papers.get("records", []):
            if isinstance(rec, dict):
                for field in ("reference_id", "pmid", "doi", "source_url", "url", "publication_id"):
                    _add(scopes[SOURCE_SCOPE_EXTERNAL], rec.get(field))
    historical = bundle.get("historical_sparql_llm_evidence") or {}
    if isinstance(historical, dict) and historical.get("status") == "CONSENSUS_7_OF_7":
        rec = historical.get("group_gene_context")
        if isinstance(rec, dict):
            _add(scopes[SOURCE_SCOPE_HISTORICAL], rec.get("gene_id_iri"))
    return {k: frozenset(v) for k, v in scopes.items()}


def _enforce_unreviewed_scientific_boundary(response: Mapping[str, Any], bundle: Mapping[str, Any]) -> None:
    """Conservative preliminary UI contract; reject unreviewed positive verdicts.

    No field in this original v0.1 schema carries a checked, claim-specific
    scientific entailment or expert-review attestation. We cannot auto-upgrade
    membership to scientific support. The deterministic UI F3/Medium proposal
    is separately displayed, and is NEVER imported into LLM screening.
    """
    for field, safe_values in {
        "proposed_f_class": {"Not assessed"},
        "proposed_hml": {"Not assessed"},
        "stock_phenotype_assessment": {"NOT_ASSESSED"},
        "source_independence": {"NOT_ASSESSED", "NOT_ESTABLISHED"},
        "disease_model_validity": {"NOT_ESTABLISHED"},
    }.items():
        if response.get(field) not in safe_values:
            raise OutputEvidenceContractError(
                f"unreviewed positive scientific evaluation blocked: {field}; "
                "a source identifier alone cannot validate a biological conclusion"
            )

    papers = bundle.get("external_papers") or {}
    original = papers.get("primary_experimental_paper_status") if isinstance(papers, dict) else None
    # Distinguish an actual negative search record from "not evaluated".
    # The existing v0.1 schema has no primary-paper NOT_ASSESSED enum; when
    # source is not assessed, HOLD and require schema evolution, not a fiction.
    if original not in {
        "NOT_IDENTIFIED_AFTER_PROJECT_CHAT_AND_EXTERNAL_SOURCE_REVIEW",
        "NOT_IDENTIFIED",
    } or response.get("candidate_specific_primary_paper_status") != "NOT_IDENTIFIED":
        raise OutputEvidenceContractError(
            "candidate-specific primary-paper status not established as NOT_IDENTIFIED "
            "by the supplied input; IDENTIFIED requires separate primary-source review"
        )

    for index, claim in enumerate(response["evidence_claims"]):
        if claim["support_status"] in SUPPORTED_STATUSES:
            raise OutputEvidenceContractError(
                f"claim[{index}] unsupported automated semantic verdict "
                f"({claim['support_status']}); identifier membership is not scientific support"
            )


def _get_expected_identity(payload: Mapping[str, Any], *,
                           trusted_ranking_authority: InProcessRankingAuthority | None,
                           ) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, Mapping) or set(payload.keys()) != {"task", "constraints", "evidence_bundle"}:
        raise OutputEvidenceContractError("unexpected LLM request input shape")
    bundle = payload.get("evidence_bundle")
    if not isinstance(bundle, dict):
        raise OutputEvidenceContractError("missing verified evidence_bundle")
    identity = bundle.get("identity")
    ranking = bundle.get("ranking")
    prov = bundle.get("provenance")
    if not isinstance(identity, dict) or not isinstance(ranking, dict) or not isinstance(prov, dict):
        raise OutputEvidenceContractError("incomplete bundle identity/ranking/provenance")
    if ranking.get("frozen_flag") is not True:
        raise OutputEvidenceContractError("ranking is not verified frozen")
    try:
        assert_live_evidence_bundle(
            authority=trusted_ranking_authority, bundle=bundle)
    except RankingProvenanceError as exc:
        raise OutputEvidenceContractError(f"ranking input live authority rejected: {exc}") from exc
    expected = {
        "disease_iri": identity["disease_iri"],
        "mouse_iri": identity["mouse_iri"],
        "family": ranking["family"],
        "final_rank": ranking["final_rank"],
    }
    return expected, bundle


def validate_provisional_llm_response(*, response: Any, input_payload: Mapping[str, Any],
                                      pinned_schema_path: Path,
                                      trusted_ranking_authority: InProcessRankingAuthority | None = None,
                                      ) -> dict[str, Any]:
    """Return bounded read-only receipt on PASS; otherwise raise (fail-closed).

    jsonschema is a required runtime dependency *only if an uploaded output is
    actually checked*. No package installation and no network invocation.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise OutputEvidenceContractError("jsonschema dependency unavailable: output cannot be accepted") from exc

    raw = Path(pinned_schema_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SCHEMA_SHA256:
        raise OutputEvidenceContractError("pinned provisional-output schema SHA256 mismatch")
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
    problems = sorted(Draft202012Validator(schema).iter_errors(response), key=lambda e: str(e.path))
    if problems:
        raise OutputEvidenceContractError("schema validation failed: " + str(problems[0].message)[:300])

    expected, bundle = _get_expected_identity(
        input_payload, trusted_ranking_authority=trusted_ranking_authority)
    observed = response["candidate_identity"]
    if type(observed["final_rank"]) is not int or observed != expected:
        raise OutputEvidenceContractError("provisional output disease/Mouse/family/rank differs from verified request")
    claims = response["evidence_claims"]
    if len(claims) > MAX_CLAIMS:
        raise OutputEvidenceContractError("too many provisional evidence claims")
    _enforce_unreviewed_scientific_boundary(response, bundle)
    allowed = collect_evidence_identifiers(bundle)
    typed = collect_typed_evidence_identifiers(bundle)
    for index, claim in enumerate(claims):
        cited = claim["evidence_identifiers"]
        if len(cited) > MAX_EVIDENCE_IDENTIFIERS_PER_CLAIM:
            raise OutputEvidenceContractError(f"claim[{index}] too many cited identifiers")
        if claim["support_status"] in SUPPORTED_STATUSES and not cited:
            raise OutputEvidenceContractError(f"claim[{index}] asserts support without an evidence identifier")
        for ref in cited:
            if len(ref) > MAX_IDENTIFIER_LENGTH or not ref.strip() or ref not in allowed:
                raise OutputEvidenceContractError(f"claim[{index}] unknown source identifier: {ref[:100]!r}")
    return {
        "gate_id": GATE_ID,
        "status": "IDENTITY_AND_INPUT_IDENTIFIER_MEMBERSHIP_PASS_NOT_SCIENTIFIC_TRUTH",
        "candidate_identity": expected,
        "input_source_identifier_count": len(allowed),
        "output_claim_count": len(claims),
        "formal_assessment_mutated": False,
        "expert_review_required": True,
        "llm_api_invoked": False,
        "network_access": False,
        "semantic_support_verification": "NOT_PERFORMED",
        "scientific_assessment_policy": "CONSERVATIVE_UNREVIEWED_SCREENING_ONLY",
        "unreviewed_positive_verdicts_accepted": False,
        "source_scope_counts_not_support": {key: len(val) for key, val in typed.items()},
    }

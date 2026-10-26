#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F04 fail-closed dynamic identity + evidence-identifier gate (no LLM call).

The fixed Draft 2020-12 schema checks syntax/structure. This additional gate
checks output identity against the exact Evidence Bundle request and citations
against explicit source fields in the verified input. A passing check only
means identity and identifier *membership* match: it cannot prove that a cited
record entails a biological claim, nor that the LLM explanation is accurate.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from kge_verified_ranking_contract_v0_1 import validate_receipt, RankingProvenanceError

GATE_ID = "KGE_8504_F04_LLM_OUTPUT_SOURCE_BOUNDARY_V0_1"
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


def _get_expected_identity(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
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
        validate_receipt(
            receipt=prov.get("ranking_verification"),
            disease_iri=identity.get("disease_iri"),
            mouse_iri=identity.get("mouse_iri"),
            ranking=ranking,
        )
    except RankingProvenanceError as exc:
        raise OutputEvidenceContractError(f"ranking input receipt rejected: {exc}") from exc
    expected = {
        "disease_iri": identity["disease_iri"],
        "mouse_iri": identity["mouse_iri"],
        "family": ranking["family"],
        "final_rank": ranking["final_rank"],
    }
    return expected, bundle


def validate_provisional_llm_response(*, response: Any, input_payload: Mapping[str, Any], pinned_schema_path: Path) -> dict[str, Any]:
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

    expected, bundle = _get_expected_identity(input_payload)
    observed = response["candidate_identity"]
    if type(observed["final_rank"]) is not int or observed != expected:
        raise OutputEvidenceContractError("provisional output disease/Mouse/family/rank differs from verified request")
    claims = response["evidence_claims"]
    if len(claims) > MAX_CLAIMS:
        raise OutputEvidenceContractError("too many provisional evidence claims")
    allowed = collect_evidence_identifiers(bundle)
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
    }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded F06 ranking receipt based on the pinned official 8504 loader.

Only trusted caller: a read-only wrapper that already imported the exact pinned
8504 source and called its verified load_all_six_family_frames().  This module
validates the returned 5,892-row frame, chosen row, loader provenance and the
pinned official source bytes.  It is not a cryptographic proof against a caller
that fabricates the loader return value, and does not establish why KGE ranked a
Mouse. No training, model rescoring, or withheld/test access.
"""
from __future__ import annotations

import hashlib
import json
import re
from weakref import WeakKeyDictionary
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

GATE_ID = "KGE_8504_F06_VERIFIED_LOADER_RANKING_RECEIPT_V0_1"
STATUS_VERIFIED = "OFFICIAL_8504_PINNED_LOADER_SELECTED_ROW_VERIFIED"
EXPECTED_OFFICIAL_SHA = "4de02002017698a3453b0567ddd44ea629945888fba3e57f05043e48aabd47ca"
OFFICIAL_FILE = (
    Path.home() / "projects/kge/bridge_node2vec_2026/"
    "streamlit_app__FX9B_GFINAL_AUDIT_CANDIDATE_V0_1_FIX1_20261009.py"
)
MOUSE_COUNT = 5892
ALLOWED_FAMILIES = frozenset(("TransE", "RotatE", "ComplEx", "node2vec", "RDF2Vec", "CompGCN"))
KNOWN_FIXED_RANK_SHA = "95e2c23fcbcf9d7aa6ffeed8ae6c7d8386ee1e41978b7a19628afc50165662d4"
KNOWN_FIXED_DISEASE = "http://purl.obolibrary.org/obo/MONDO_0005148"
KNOWN_FIXED_FAMILY = "node2vec"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class RankingProvenanceError(RuntimeError):
    pass


class InProcessRankingAuthority:
    """Opaque, NON-SERIALIZABLE authority usable only in this Python process.

    Issued only after the trusted 8504 wrapper calls the pinned helper loader
    and this module validates the selected candidate.  A constructor call by
    itself does NOT register an authority.  This is NOT a cryptographic digital
    signature and must not be accepted across process/broker trust boundaries.
    """
    __slots__ = ("__weakref__",)

    def __reduce__(self):
        raise TypeError("InProcessRankingAuthority cannot be serialized")

    def __reduce_ex__(self, protocol):
        raise TypeError("InProcessRankingAuthority cannot be serialized")


# A weak, in-process authorization registry. The exported Evidence JSON never
# contains or can reconstruct these object identities. If a different process
# receives a JSON receipt, it MUST call the pinned official loader itself.
_ISSUED_AUTHORITIES: WeakKeyDictionary = WeakKeyDictionary()


def _canonical_sha(obj: Any) -> str:
    try:
        return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    except (TypeError, ValueError) as exc:
        raise RankingProvenanceError("authority binding is not canonical JSON") from exc


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_string(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise RankingProvenanceError(f"missing ranking provenance field: {field}")
    return value


def _receipt_digest(d: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_official_loaded_row(*, loaded: Mapping[str, Any], family: str, final_rank: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate ranking and a row/source receipt from the OFFICIAL, PINNED loader.

    Caller must use official.verified_helper().load_all_six_family_frames().
    The verification source file is fixed, not supplied by untrusted input.
    """
    if _file_sha256(OFFICIAL_FILE) != EXPECTED_OFFICIAL_SHA:
        raise RankingProvenanceError("official 8504 source missing or SHA256 mismatch")
    if not isinstance(loaded, Mapping):
        raise RankingProvenanceError("verified loader returned invalid mapping")
    if family not in ALLOWED_FAMILIES or type(final_rank) is not int or not 1 <= final_rank <= MOUSE_COUNT:
        raise RankingProvenanceError("unsupported ranking family or rank")
    disease_iri = _require_string(loaded, "disease_iri")
    if not disease_iri.startswith("http://purl.obolibrary.org/obo/MONDO_"):
        raise RankingProvenanceError("verified disease IRI missing/invalid")
    frames = loaded.get("frames")
    provs = loaded.get("provenance")
    if not isinstance(frames, Mapping) or not isinstance(provs, Mapping):
        raise RankingProvenanceError("verified loader frames or provenance missing")
    df, provenance = frames.get(family), provs.get(family)
    if not isinstance(df, pd.DataFrame) or not isinstance(provenance, Mapping):
        raise RankingProvenanceError("ranking frame or family provenance missing")
    if len(df) != MOUSE_COUNT or not {"final_rank", "mouse_iri"}.issubset(df.columns):
        raise RankingProvenanceError("ranking frame row count or columns invalid")
    ranks = pd.to_numeric(df["final_rank"], errors="raise")
    if not ranks.notna().all() or (ranks % 1 != 0).any():
        raise RankingProvenanceError("ranking contains noninteger ranks")
    rank_ints = ranks.astype(int)
    if rank_ints.nunique() != MOUSE_COUNT or int(rank_ints.min()) != 1 or int(rank_ints.max()) != MOUSE_COUNT:
        raise RankingProvenanceError("ranking does not contain each frozen rank exactly once")
    mouse_ids = df["mouse_iri"].astype(str)
    if mouse_ids.nunique() != MOUSE_COUNT or not mouse_ids.str.startswith("http://metadb.riken.jp/db/rikenbrc_mouse/").all():
        raise RankingProvenanceError("ranking Mouse identities are not 5,892 unique absolute IRIs")
    hits = df.loc[rank_ints == final_rank]
    if len(hits) != 1:
        raise RankingProvenanceError("chosen rank not unique")
    row = hits.iloc[0]
    mouse_iri = str(row["mouse_iri"])
    rank_sha = _require_string(provenance, "family_ranking_sha256").lower()
    if not SHA256_RE.fullmatch(rank_sha):
        raise RankingProvenanceError("ranking provenance does not contain a SHA256")
    if disease_iri == KNOWN_FIXED_DISEASE and family == KNOWN_FIXED_FAMILY and rank_sha != KNOWN_FIXED_RANK_SHA:
        raise RankingProvenanceError("known fixed node2vec ranking SHA256 mismatch")
    ranking = {
        "family": family,
        "final_rank": final_rank,
        "gene_rank": str(row.get("gene_rank", "")),
        "phenotype_rank": str(row.get("phenotype_rank", "")),
        "integrated_rank": str(row.get("integrated_rank", "")),
        "route_state": str(loaded.get("route_state", "")),
        "family_ranking_sha256": rank_sha,
    }
    receipt = {
        "gate_id": GATE_ID,
        "status": STATUS_VERIFIED,
        "official_8504_sha256": EXPECTED_OFFICIAL_SHA,
        "source_contract": "PINNED_OFFICIAL_HELPER_LOADER_ROW_AND_PROVENANCE",
        "ranking_source_byte_rechecked_here": False,
        "ranking_source_exactness_authority": "OFFICIAL_VERIFIED_HELPER",
        "family_ranking_sha256": rank_sha,
        "disease_iri": disease_iri,
        "mouse_iri": mouse_iri,
        "family": family,
        "final_rank": final_rank,
        "frame_mouse_count": MOUSE_COUNT,
        "selected_row_count": 1,
    }
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    return ranking, receipt


def verify_official_loaded_row_trusted(*, loaded: Mapping[str, Any], family: str, final_rank: int) -> tuple[dict[str, Any], dict[str, Any], InProcessRankingAuthority]:
    """Issue in-process context while handling the officially loaded frame.

    Only the SHA-pinned Streamlit wrapper may supply `loaded`, obtained directly
    via `official.verified_helper().load_all_six_family_frames()`.  Untrusted
    Python code supplied as `loaded` is outside this trust boundary; neither
    the receipt nor the authority object proves a digital signature.
    """
    ranking, receipt = verify_official_loaded_row(
        loaded=loaded, family=family, final_rank=final_rank
    )
    context = InProcessRankingAuthority()
    _ISSUED_AUTHORITIES[context] = {
        "disease_iri": receipt["disease_iri"],
        "mouse_iri": receipt["mouse_iri"],
        "ranking_sha": _canonical_sha(ranking),
        "receipt_sha": _canonical_sha(receipt),
        "bound_bundle_sha": None,
    }
    return ranking, receipt, context


def _authority_for(*, authority: InProcessRankingAuthority | None,
                   disease_iri: str, mouse_iri: str,
                   ranking: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    try:
        record = _ISSUED_AUTHORITIES.get(authority)
    except TypeError:
        record = None
    if record is None:
        raise RankingProvenanceError("missing live in-process official-loader authority; unsigned JSON receipt alone is not trusted")
    if _file_sha256(OFFICIAL_FILE) != EXPECTED_OFFICIAL_SHA:
        raise RankingProvenanceError("pinned official 8504 code changed after live authority issuance")
    if record["disease_iri"] != disease_iri or record["mouse_iri"] != mouse_iri:
        raise RankingProvenanceError("live authority candidate identity mismatch")
    ranking_raw = dict(ranking)
    if "frozen_flag" in ranking_raw:
        if ranking_raw.pop("frozen_flag") is not True:
            raise RankingProvenanceError("live authority rejects unverified frozen flag")
    if record["ranking_sha"] != _canonical_sha(ranking_raw) or record["receipt_sha"] != _canonical_sha(receipt):
        raise RankingProvenanceError("live authority ranking/receipt mutated or replaced")
    validate_receipt(receipt=receipt, disease_iri=disease_iri, mouse_iri=mouse_iri, ranking=ranking)
    return record


def assert_live_ranking_authority(*, authority: InProcessRankingAuthority | None,
                                  disease_iri: str, mouse_iri: str,
                                  ranking: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
    """Authorization, not merely an unsigned receipt consistency check."""
    _authority_for(authority=authority, disease_iri=disease_iri, mouse_iri=mouse_iri,
                   ranking=ranking, receipt=receipt)


def bind_live_evidence_bundle(*, authority: InProcessRankingAuthority | None,
                              bundle: Mapping[str, Any]) -> None:
    """One-time bind: verified ranking -> exact locally constructed Evidence."""
    identity = bundle.get("identity", {})
    ranking = bundle.get("ranking", {})
    receipt = bundle.get("provenance", {}).get("ranking_verification", {})
    record = _authority_for(
        authority=authority, disease_iri=identity.get("disease_iri"),
        mouse_iri=identity.get("mouse_iri"), ranking=ranking, receipt=receipt)
    digest = _canonical_sha(bundle)
    if record["bound_bundle_sha"] is not None:
        raise RankingProvenanceError("live ranking authority cannot be rebound to an Evidence Bundle")
    record["bound_bundle_sha"] = digest


def assert_live_evidence_bundle(*, authority: InProcessRankingAuthority | None,
                                bundle: Mapping[str, Any]) -> None:
    """Reject copied, modified, or externally supplied unsigned Evidence JSON."""
    identity = bundle.get("identity", {})
    ranking = bundle.get("ranking", {})
    receipt = bundle.get("provenance", {}).get("ranking_verification", {})
    record = _authority_for(
        authority=authority, disease_iri=identity.get("disease_iri"),
        mouse_iri=identity.get("mouse_iri"), ranking=ranking, receipt=receipt)
    if record["bound_bundle_sha"] is None:
        raise RankingProvenanceError("Evidence Bundle has no in-process authorized binding")
    if record["bound_bundle_sha"] != _canonical_sha(bundle):
        raise RankingProvenanceError("Evidence Bundle changed after live official-loader authorization")


def validate_receipt(*, receipt: Mapping[str, Any] | None, disease_iri: str, mouse_iri: str, ranking: Mapping[str, Any]) -> dict[str, Any]:
    """Unsigned JSON INTEGRITY ONLY. Never use this as authorization alone."""
    if not isinstance(receipt, Mapping):
        raise RankingProvenanceError("ranking verification receipt absent")
    clean = dict(receipt)
    digest = clean.pop("receipt_sha256", None)
    if not isinstance(digest, str) or digest != _receipt_digest(clean):
        raise RankingProvenanceError("ranking receipt content digest invalid")
    if clean.get("gate_id") != GATE_ID or clean.get("status") != STATUS_VERIFIED:
        raise RankingProvenanceError("ranking receipt status invalid")
    if clean.get("official_8504_sha256") != EXPECTED_OFFICIAL_SHA:
        raise RankingProvenanceError("ranking receipt not tied to pinned official source")
    if clean.get("source_contract") != "PINNED_OFFICIAL_HELPER_LOADER_ROW_AND_PROVENANCE":
        raise RankingProvenanceError("ranking receipt source contract invalid")
    if clean.get("ranking_source_exactness_authority") != "OFFICIAL_VERIFIED_HELPER":
        raise RankingProvenanceError("ranking verification authority not official loader")
    if clean.get("ranking_source_byte_rechecked_here") is not False:
        raise RankingProvenanceError("invalid independent-source-byte claim")
    if clean.get("disease_iri") != disease_iri or clean.get("mouse_iri") != mouse_iri:
        raise RankingProvenanceError("ranking receipt candidate identity mismatch")
    for k in ("family", "final_rank", "family_ranking_sha256"):
        if type(clean.get(k)) is not type(ranking.get(k)) or clean.get(k) != ranking.get(k):
            raise RankingProvenanceError(f"ranking receipt mismatch: {k}")
    if clean.get("frame_mouse_count") != MOUSE_COUNT or clean.get("selected_row_count") != 1:
        raise RankingProvenanceError("ranking receipt count invalid")
    if not SHA256_RE.fullmatch(str(clean.get("family_ranking_sha256", ""))):
        raise RankingProvenanceError("ranking family source SHA invalid")
    if disease_iri == KNOWN_FIXED_DISEASE and clean["family"] == KNOWN_FIXED_FAMILY:
        if clean["family_ranking_sha256"] != KNOWN_FIXED_RANK_SHA:
            raise RankingProvenanceError("fixed family ranking SHA mismatch")
    return dict(receipt)

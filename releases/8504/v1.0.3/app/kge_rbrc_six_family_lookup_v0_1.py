"""Lookup a stock's six saved KGE ranks in the already verified loader frames.

This module does not train, score, rank, access the network, or open research
sources. It only selects existing final_rank rows using a canonical Mouse IRI.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence


MOUSE_PREFIX = "http://metadb.riken.jp/db/rikenbrc_mouse/"


class RbrcLookupHold(ValueError):
    """An identity or ranking-contract failure; never a biological negative."""


def normalize_rbrc_id(value: str) -> str:
    if not isinstance(value, str):
        raise RbrcLookupHold("HOLD_RBRC_ID_NOT_TEXT")
    candidate = value.strip().upper()
    if not 5 <= len(candidate) <= 48:
        raise RbrcLookupHold("HOLD_RBRC_ID_LENGTH")
    if not re.fullmatch(r"RBRC(?:-?[A-Z0-9]+){1,5}", candidate, flags=re.ASCII):
        raise RbrcLookupHold("HOLD_RBRC_ID_FORMAT")
    return candidate


def _rank_as_int(value: Any, *, mouse_n: int) -> int:
    if isinstance(value, bool):
        raise RbrcLookupHold("HOLD_RANK_TYPE")
    text_value = str(value).strip()
    if re.fullmatch(r"[1-9][0-9]*", text_value, flags=re.ASCII):
        rank = int(text_value)
    elif isinstance(value, (float,)) and math.isfinite(value) and value.is_integer():
        rank = int(value)
    else:
        raise RbrcLookupHold("HOLD_RANK_TYPE")
    if not 1 <= rank <= mouse_n:
        raise RbrcLookupHold("HOLD_RANK_OUT_OF_RANGE")
    return rank


def lookup_rbrc_six_ranks(
    *,
    loaded: Mapping[str, Any],
    family_order: Sequence[str],
    rbrc_id: str,
    mouse_n: int = 5892,
) -> list[dict[str, Any]]:
    """Exact-only read of saved ranks; no filtering-based reranking.

    ``loaded`` MUST originate from the existing pinned six-family loader. This
    helper is not an independent provenance verifier: the caller must verify
    each selected rank row using its existing trusted in-process authority.
    """
    identity = normalize_rbrc_id(rbrc_id)
    names = tuple(family_order)
    if len(names) != 6 or len(set(names)) != 6 or not all(isinstance(x, str) and x for x in names):
        raise RbrcLookupHold("HOLD_FAMILY_ORDER_NOT_SIX")
    if not isinstance(mouse_n, int) or mouse_n < 1:
        raise RbrcLookupHold("HOLD_MOUSE_COUNT")
    if not isinstance(loaded, Mapping) or not isinstance(loaded.get("frames"), Mapping):
        raise RbrcLookupHold("HOLD_VERIFIED_LOADER_FRAMES_MISSING")
    expected_iri = MOUSE_PREFIX + identity
    rows = []
    hit_counts = []
    for family in names:
        frame = loaded["frames"].get(family)
        if frame is None or not {"mouse_iri", "final_rank"}.issubset(frame.columns):
            raise RbrcLookupHold("HOLD_FAMILY_FRAME_SCHEMA")
        if len(frame) != mouse_n:
            raise RbrcLookupHold("HOLD_FAMILY_FRAME_SIZE")
        matches = frame.loc[frame["mouse_iri"].astype(str).eq(expected_iri)]
        hit_counts.append(len(matches))
        if len(matches) > 1:
            raise RbrcLookupHold("HOLD_DUPLICATE_RBRC_ID")
        if len(matches) == 1:
            row = matches.iloc[0]
            rows.append({
                "family": family,
                "rbrc_id": identity,
                "mouse_iri": expected_iri,
                "final_rank": _rank_as_int(row["final_rank"], mouse_n=mouse_n),
            })
    if all(count == 0 for count in hit_counts):
        raise RbrcLookupHold("HOLD_RBRC_NOT_IN_VERIFIED_MOUSE_UNIVERSE")
    if any(count != 1 for count in hit_counts) or len(rows) != len(names):
        raise RbrcLookupHold("HOLD_CROSS_FAMILY_MOUSE_IDENTITY_MISMATCH")
    return rows

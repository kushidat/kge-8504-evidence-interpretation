#!/usr/bin/env python3
"""V14 order 5: immutable provisional output archive; no network, API or BYOK.

This module is called only after the existing Stage4E/Stage4C successful result.
The caller's existing 8504 pinned candidate is the authority, never the LLM.
It never updates 8504 evidence, ranking, G4, F/HML, or 8510 sources.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

ARCHIVE_ROOT = (Path.home() / 'projects/mondo_eval/release_records/8504_8510'
                / 'isolated/8504_8510_STAGE5_RESULTS_ONLY')
EXPECTED_STATUS = 'STAGE4C_LOCAL_8510_LLM_PROVISIONAL_NOT_SCIENTIFIC_VALIDATION'
EXPECTED_JSON_RECORD = '8510_manual_source_interpretation_provisional'
EXPECTED_JSON_STATUS = 'LLM_PROVISIONAL_NOT_SCIENTIFIC_VALIDATION'
ID_KEYS = ('disease_iri', 'mouse_iri', 'rbrc_id', 'family', 'final_rank', 'input_sha256')
_SECRET_PATTERN = re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b')


class Stage5ArchiveHold(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_identity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise Stage5ArchiveHold('SELECTED_CANDIDATE_INVALID')
    fields = {k: candidate.get(k) for k in ID_KEYS}
    if not re.fullmatch(r'https?://purl\.obolibrary\.org/obo/MONDO_[0-9]{7}', str(fields['disease_iri'])):
        raise Stage5ArchiveHold('DISEASE_ID_INVALID')
    if not re.fullmatch(r'https?://metadb\.riken\.jp/db/rikenbrc_mouse/RBRC[0-9A-Za-z-]{2,40}', str(fields['mouse_iri'])):
        raise Stage5ArchiveHold('MOUSE_ID_INVALID')
    if not re.fullmatch(r'RBRC[0-9A-Za-z-]{2,40}', str(fields['rbrc_id'])):
        raise Stage5ArchiveHold('RBRC_ID_INVALID')
    if not str(fields['mouse_iri']).endswith('/' + str(fields['rbrc_id'])):
        raise Stage5ArchiveHold('MOUSE_RBRC_NOT_BOUND')
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,32}', str(fields['family'])):
        raise Stage5ArchiveHold('FAMILY_INVALID')
    if type(fields['final_rank']) is not int or not (1 <= fields['final_rank'] <= 5892):
        raise Stage5ArchiveHold('RANK_INVALID')
    if not re.fullmatch(r'[0-9a-f]{64}', str(fields['input_sha256'])):
        raise Stage5ArchiveHold('INPUT_SHA_INVALID')
    return fields


def validate_output(out: Mapping[str, Any], selected_candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Bind original 8510 output to selected 8504 candidate; no source discovery."""
    selected = _safe_identity(selected_candidate)
    if not isinstance(out, Mapping) or out.get('status') != EXPECTED_STATUS:
        raise Stage5ArchiveHold('NOT_COMPLETED_8510_RESULT')
    response_candidate = _safe_identity(out.get('candidate', {}))
    if selected != response_candidate or out.get('input_sha256') != selected['input_sha256']:
        raise Stage5ArchiveHold('CANDIDATE_BOUNDARY_MISMATCH')
    if (out.get('scientific_validation') != 'NOT_PERFORMED'
            or out.get('formal_evidence_mutated') is not False
            or out.get('ranking_mutated') is not False
            or out.get('api_key_exported') is not False):
        raise Stage5ArchiveHold('SCIENCE_OR_FORMAL_STATE_INVALID')
    if type(out.get('api_calls')) is not int or out['api_calls'] != 1 or out.get('retry_count') != 0:
        raise Stage5ArchiveHold('API_CALL_RECEIPT_INVALID')
    if not re.fullmatch(r'[0-9a-f]{64}', str(out.get('attempt_id', ''))):
        raise Stage5ArchiveHold('ATTEMPT_ID_INVALID')
    stamp = out.get('timestamp', '')
    if not isinstance(stamp, str) or not re.fullmatch(r'20[0-9]{6}_[0-9]{6}', stamp):
        raise Stage5ArchiveHold('STAMP_INVALID')
    md, raw = out.get('markdown'), out.get('json')
    if not isinstance(md, str) or not isinstance(raw, str):
        raise Stage5ArchiveHold('RESULT_BYTES_MISSING')
    mb, jb = md.encode('utf-8'), raw.encode('utf-8')
    if not (len(mb) <= 20_000_000 and len(jb) <= 20_000_000 and mb and jb):
        raise Stage5ArchiveHold('RESULT_SIZE_INVALID')
    if _SECRET_PATTERN.search(md) or _SECRET_PATTERN.search(raw):
        raise Stage5ArchiveHold('SECRET_PATTERN_IN_RESULT')
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise Stage5ArchiveHold('RESULT_JSON_INVALID') from exc
    if not isinstance(obj, dict):
        raise Stage5ArchiveHold('RESULT_JSON_NOT_OBJECT')
    if obj.get('record_type') != EXPECTED_JSON_RECORD or obj.get('status') != EXPECTED_JSON_STATUS:
        raise Stage5ArchiveHold('8510_RECORD_TYPE_INVALID')
    if obj.get('model') != 'gpt-6-luna' or out.get('model') != 'gpt-6-luna':
        raise Stage5ArchiveHold('MODEL_MISMATCH')
    if obj.get('source_coverage') != 'FULL_TEXT_FOR_TEXT_FILES' or obj.get('input_truncated_for_llm') is not False:
        raise Stage5ArchiveHold('SOURCE_COVERAGE_INVALID')
    records = obj.get('input_files')
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise Stage5ArchiveHold('INPUT_FILES_INVALID')
    rec = records[0]
    if rec.get('sha256') != selected['input_sha256']:
        raise Stage5ArchiveHold('SOURCE_FILE_SHA_MISMATCH')
    expected_name = ('EVIDENCE_LLM_INPUT__' + selected['disease_iri'].rsplit('/', 1)[-1]
                     + '__' + selected['family'] + '__rank' + str(selected['final_rank'])
                     + '__' + selected['rbrc_id'] + '.json')
    if rec.get('file_name') != expected_name:
        raise Stage5ArchiveHold('SOURCE_FILENAME_BOUNDARY_MISMATCH')
    forbidden_keys = {'api_key', 'byok', 'access_token', 'authorization', 'client_secret'}
    def contains_secret_key(value):
        if isinstance(value, dict):
            return any(str(k).lower() in forbidden_keys or contains_secret_key(v)
                       for k,v in value.items())
        if isinstance(value, list):
            return any(contains_secret_key(v) for v in value)
        return False
    if contains_secret_key(obj):
        raise Stage5ArchiveHold('SENSITIVE_OUTPUT_KEY_REFUSED')
    text = obj.get('interpretation_text')
    if not isinstance(text, str) or not text.strip() or text != out.get('interpretation_text') or text not in md:
        raise Stage5ArchiveHold('INTERPRETATION_BODY_MISMATCH')
    if not isinstance(out.get('quality'), dict) or obj.get('biology_quality_screen') != out['quality']:
        raise Stage5ArchiveHold('QUALITY_SCREEN_MISMATCH')
    if not isinstance(obj.get('public_annotations'), dict):
        raise Stage5ArchiveHold('PUBLIC_ANNOTATIONS_MISSING')
    if obj.get('scientific_validation') == 'VALIDATED':
        raise Stage5ArchiveHold('SCIENTIFIC_VALIDITY_ESCALATION')
    source_status = str(out['quality'].get('source_status', 'REVIEW_REQUIRED'))[:120]
    if not re.fullmatch(r'[A-Za-z0-9 _./:-]{1,120}', source_status):
        source_status = 'REVIEW_REQUIRED'
    base = ('8510_PROVISIONAL__' + selected['disease_iri'].rsplit('/', 1)[-1]
            + '__' + selected['family'] + '__rank' + str(selected['final_rank'])
            + '__' + selected['rbrc_id'] + '__gpt-6-luna__' + stamp
            + '__input' + selected['input_sha256'][:12]
            + '__out' + sha256(jb)[:10])
    return {'candidate': selected, 'md_bytes': mb, 'json_bytes': jb,
            'source_status': source_status, 'base': base,
            'attempt_sha': out['attempt_id'], 'output_timestamp': stamp,
            'json_sha256': sha256(jb), 'markdown_sha256': sha256(mb)}


def _private_folder(root: Path) -> None:
    if root.is_symlink():
        raise Stage5ArchiveHold('ARCHIVE_ROOT_SYMLINK')
    parent = root.parent
    if not parent.is_dir() or parent.is_symlink():
        raise Stage5ArchiveHold('ARCHIVE_PARENT_NOT_VERIFIED')
    if not root.exists():
        root.mkdir(mode=0o700, exist_ok=False)
    st = root.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077:
        raise Stage5ArchiveHold('ARCHIVE_ROOT_NOT_PRIVATE')


def save_immutable(out: Mapping[str, Any], selected: Mapping[str, Any], *,
                   archive_root: Path | None = None) -> dict[str, Any]:
    """Explicit-only on-disk save, never replacing a file or deleting a failed attempt.

    archive_root is injectable for isolated test cases. In the UI it is never passed.
    """
    ready = validate_output(out, selected)   # no file operations before boundary check
    root = ARCHIVE_ROOT if archive_root is None else Path(archive_root)
    _private_folder(root)
    dest = root / ready['base']
    if os.path.lexists(dest):
        raise Stage5ArchiveHold('RESULT_ALREADY_ARCHIVED_NO_OVERWRITE')
    dest.mkdir(mode=0o700, exist_ok=False)
    basename = ready['base']
    manifest = {
        'archive_status': 'IMMUTABLE_USER_APPROVED_PROVISIONAL_ONLY',
        'scientific_validation': 'NOT_PERFORMED',
        'provenance_note': 'SOURCE_URLS_AND_LLM_CLAIMS_REQUIRE_INDEPENDENT_REVIEW',
        'candidate': ready['candidate'],
        'attempt_sha256': ready['attempt_sha'],
        'input_sha256': ready['candidate']['input_sha256'],
        'timestamp_jst': ready['output_timestamp'],
        'public_source_status_as_reported': ready['source_status'],
        'files': {
            basename + '.md': {'sha256': ready['markdown_sha256'], 'bytes': len(ready['md_bytes'])},
            basename + '.json': {'sha256': ready['json_sha256'], 'bytes': len(ready['json_bytes'])},
        },
        'formal_evidence_mutated': False,
        'ranking_mutated': False,
        'byok_saved': False,
        'api_calls_during_archival': 0,
    }
    payloads = {
        basename + '.md': ready['md_bytes'],
        basename + '.json': ready['json_bytes'],
        'RECEIPT_PROVISIONAL.json': (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode('utf-8'),
    }
    for name, blob in payloads.items():
        with (dest / name).open('xb') as fh:
            fh.write(blob)
        (dest / name).chmod(0o600)
    for name, blob in payloads.items():
        p = dest / name
        if p.is_symlink() or p.read_bytes() != blob:
            raise Stage5ArchiveHold('ARCHIVE_READBACK_MISMATCH')
    return {'status': 'STAGE5_NO_OVERWRITE_ARCHIVE_READBACK_PASS',
            'destination': str(dest), 'file_count': len(payloads),
            'json_sha256': ready['json_sha256'],
            'markdown_sha256': ready['markdown_sha256'],
            'api_calls_during_archival': 0,
            'scientific_validation': 'NOT_PERFORMED'}


def render_stage5_controls(*, st: Any, out: Mapping[str, Any], current: Mapping[str, Any]) -> None:
    """A supplementary save action after Stage4E's existing UI; no new API path."""
    st.subheader('8510 provisional result: source and immutable save (Stage5)')
    try:
        ready = validate_output(out, current['candidate'])
    except (Stage5ArchiveHold, KeyError, TypeError):
        st.error('STAGE5_RESULT_VALIDATION_HOLD: no save or external API call')
        return
    st.warning('8510 output is provisional. Source URLs, allele/phenotype claims, and citations are not independently validated; KGE rank causation is not established.')
    st.json({'candidate': ready['candidate'], 'input_sha256': ready['candidate']['input_sha256'],
             'public_source_status_as_reported': ready['source_status'],
             'markdown_sha256': ready['markdown_sha256'], 'json_sha256': ready['json_sha256'],
             'scientific_validation': 'NOT_PERFORMED',
             'auto_promotion_to_f_hml_g4': False})
    st.caption('Existing Download Markdown/JSON buttons above are unchanged. The button below writes a private, no-overwrite pair and SHA receipt to an isolated results-only directory; it never changes KGE Evidence.')
    if st.button('Save these provisional Markdown/JSON files without overwrite', key='stage5_explicit_archive_once'):
        try:
            receipt = save_immutable(out, current['candidate'])
        except (Stage5ArchiveHold, OSError):
            st.error('STAGE5_SAVE_HOLD_NO_OVERWRITE: existing or invalid archive; no retry or automatic replacement')
        else:
            st.success('STAGE5_ARCHIVE_READBACK_PASS; NO_API=YES')
            st.json(receipt)

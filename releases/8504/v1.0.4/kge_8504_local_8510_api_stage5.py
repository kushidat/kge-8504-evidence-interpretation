#!/usr/bin/env python3
"""Approved V14 order 4: in-process 8504 -> pinned 8510 V10 API functions.

No Docker/Colima, no automatic sends. BYOK is submitted once to this isolated
8504 view, never read from or copied out of the existing 8510 container.
The full encrypted BYOK-management integration belongs to V14 order 5.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Callable, Mapping

from kge_8504_stage4_single_candidate_preview import selected_payload_details, load_source_bridge
from kge_8504_stage5_immutable_result import render_stage5_controls

STAGE3_DIR = Path.home() / 'projects/mondo_eval/release_records/8504_8510/isolated/8504_8510_SHARED_8510_CORE_STAGE3_20261107_V01'
ATTEMPT_DIR = Path.home() / 'projects/mondo_eval/release_records/8504_8510/isolated/8504_8510_STAGE4C_ATTEMPT_GUARD_ONLY'
MODEL = 'gpt-6-luna'
ENABLE_VALUE = 'EXPLICIT_V14_SINGLE_PAID_API_CALL_APPROVED'
MAX_SCOPE_CHARS = 500


class DirectAPIHold(RuntimeError):
    pass


class Stage4EPhaseHold(DirectAPIHold):
    """A phase + fixed category only; never formats the original exception."""
    PHASE_ALLOWLIST = ('GATE_CHECK', 'PREPARE_INPUT', 'ATTEMPT_GUARD', 'PUBLIC_LOOKUP', 'PROMPT_BUILD', 'SOURCE_SIZE_GATE', 'CLIENT_CONSTRUCT', 'PROVIDER_REQUEST', 'PROVIDER_RESPONSE', 'QUALITY_SCREEN', 'SERIALIZE_RESULT')
    CATEGORIES = {'BYOK_OR_CONSENT', 'DUPLICATE_GUARD', 'SOURCE_BOUND',
                  'NETWORK', 'TIMEOUT', 'PROVIDER_AUTH', 'PROVIDER_RATE_LIMIT',
                  'PROVIDER_REJECTED', 'POLICY_HOLD', 'OTHER_EXCEPTION'}

    def __init__(self, phase, category):
        self.phase = phase if phase in self.PHASE_ALLOWLIST else 'GATE_CHECK'
        self.category = category if category in self.CATEGORIES else 'OTHER_EXCEPTION'
        super().__init__('STAGE4E_PHASE=' + self.phase + '; CLASS=' + self.category)


def _stage4e_safe_class(exc):
    """Map exception *type* or fixed internal code, never inspect text for output."""
    if isinstance(exc, DirectAPIHold):
        text = str(exc)
        if text in ('DUPLICATE_API_ATTEMPT_NO_AUTO_RETRY',):
            return 'DUPLICATE_GUARD'
        if text in ('PAID_API_LOCKED_BY_DEFAULT', 'EXPLICIT_SINGLE_CALL_CONSENT_REQUIRED',
                    'BYOK_REQUIRED_FOR_THIS_SESSION'):
            return 'BYOK_OR_CONSENT'
        if text in ('PUBLIC_CONTEXT_EXCEEDS_FULL_SOURCE_BOUND',
                    'ONLY_SINGLE_TEXT_INPUT_ALLOWED', 'SOURCE_NOT_FULL_TEXT',
                    'INPUT_SHA_REBIND_FAILED', 'PINNED_MODEL_MISMATCH'):
            return 'SOURCE_BOUND'
        return 'POLICY_HOLD'
    typ = type(exc).__name__
    if typ in ('AuthenticationError', 'PermissionDeniedError'):
        return 'PROVIDER_AUTH'
    if typ in ('RateLimitError',):
        return 'PROVIDER_RATE_LIMIT'
    if typ in ('APIStatusError', 'BadRequestError', 'UnprocessableEntityError'):
        return 'PROVIDER_REJECTED'
    if typ in ('APITimeoutError', 'TimeoutError', 'ConnectTimeout'):
        return 'TIMEOUT'
    if typ in ('APIConnectionError', 'ConnectionError', 'ConnectError',
               'NetworkError', 'SSLError'):
        return 'NETWORK'
    return 'OTHER_EXCEPTION'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_filename(candidate: Mapping[str, Any]) -> str:
    return ('EVIDENCE_LLM_INPUT__' + candidate['disease_iri'].rsplit('/', 1)[-1]
            + '__' + str(candidate['family']) + '__rank' + str(candidate['final_rank'])
            + '__' + candidate['rbrc_id'] + '.json')


def _stage5_preload_verified_v10_role_module(shared, bridge):
    """Load exactly one lazily imported, SHA-pinned V10 role parser.

    Stage3's temporary sys.path is restored after import, whereas the V10 public
    lookup imports source_role_v09 inside a function only on first live request.
    Preloading here during NO-API preparation avoids a post-attempt import error.
    Never alters on-disk originals or contacts any network.
    """
    import importlib.util as _iutil
    import sys as _sys
    name = 'source_role_v09'
    with bridge._IMPORT_LOCK:
        entry = bridge._pins().get(name + '.py')
        source = shared.root / (name + '.py')
        if (not isinstance(entry, dict) or source.is_symlink()
                or not source.is_file()
                or source.stat().st_size != entry.get('size_bytes')
                or sha(source.read_bytes()) != entry.get('sha256')):
            raise DirectAPIHold('PINNED_V10_LAZY_ROLE_SOURCE_INVALID')
        existing = _sys.modules.get(name)
        if existing is not None:
            if (not getattr(existing, '__file__', None)
                    or Path(existing.__file__).resolve() != source.resolve()):
                raise DirectAPIHold('PINNED_V10_LAZY_ROLE_MODULE_CONFLICT')
            bridge._check_preimported_modules(shared.root)
            return
        spec = _iutil.spec_from_file_location(name, source)
        if spec is None or spec.loader is None:
            raise DirectAPIHold('PINNED_V10_LAZY_ROLE_IMPORT_UNAVAILABLE')
        module = _iutil.module_from_spec(spec)
        _sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            bridge._check_preimported_modules(shared.root)
        except BaseException:
            _sys.modules.pop(name, None)
            raise



def prepare_selected(bundle: Mapping[str, Any], input_bytes: bytes, *,
                     stage3_dir: Path | None = None, scope_note: str = '') -> dict:
    """Read-only V10 source preparation, not an invocation or API credential read."""
    if type(scope_note) is not str or len(scope_note) > MAX_SCOPE_CHARS or '\x00' in scope_note:
        raise DirectAPIHold('INVALID_SCOPE_NOTE')
    candidate = selected_payload_details(bundle, input_bytes)
    bridge = load_source_bridge(Path(stage3_dir) if stage3_dir is not None else STAGE3_DIR)
    shared = bridge.load_pinned_shared_core()
    _stage5_preload_verified_v10_role_module(shared, bridge)
    pairs = [(input_filename(candidate), input_bytes)]
    prepared = shared.prepare_messages(pairs, scope_note=scope_note)
    if prepared['input_file_count'] != 1 or prepared['image_count'] != 0:
        raise DirectAPIHold('ONLY_SINGLE_TEXT_INPUT_ALLOWED')
    if prepared['coverage'] != 'FULL_TEXT_FOR_TEXT_FILES':
        raise DirectAPIHold('SOURCE_NOT_FULL_TEXT')
    if prepared['records'][0]['sha256'] != candidate['input_sha256']:
        raise DirectAPIHold('INPUT_SHA_REBIND_FAILED')
    if shared.core.MODEL != MODEL:
        raise DirectAPIHold('PINNED_MODEL_MISMATCH')
    return {'candidate': candidate, 'pairs': pairs, 'shared': shared,
            'records': prepared['records'], 'coverage': prepared['coverage'],
            'prepared_bytes': prepared['full_source_bytes'],
            'input_sha256': candidate['input_sha256'],
            'source_status': 'IN_PROCESS_PINNED_8510_V10_12_OF_12_VERIFIED',
            'network_calls': 0, 'api_calls': 0}


def safe_preview(prepared: dict) -> dict:
    """Never expose full prompt or key in a UI receipt."""
    return {'status': 'STAGE4C_LOCAL_8510_API_PREPARED_NO_API',
            'candidate': prepared['candidate'], 'input_sha256': prepared['input_sha256'],
            'prepared_utf8_bytes': prepared['prepared_bytes'],
            'reused_8510_existing_functions': True,
            'docker_required': False, 'colima_required': False,
            'byok_read': False, 'external_http_calls': 0, 'llm_api_calls': 0,
            'scientific_validation': 'NOT_PERFORMED',
            'formal_evidence_mutated': False, 'ranking_mutated': False}


@contextmanager
def _reserve_user_click(candidate: dict, scope: str, attempt_dir: Path):
    """Only concurrent requests are duplicates; historical attempts never block.

    A fresh explicit Streamlit form submission generates a fresh attempt ID.
    The lock is bound to the candidate, not scope text, so changing optional
    instructions cannot evade the in-flight lock. Previous V1 markers remain
    untouched. All records are metadata only, no prompt or BYOK value.
    """
    import fcntl
    import secrets
    from datetime import datetime, timezone
    attempt_dir = Path(attempt_dir)
    if attempt_dir.is_symlink():
        raise DirectAPIHold('ATTEMPT_GUARD_SYMLINK')
    try:
        attempt_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise DirectAPIHold('ATTEMPT_GUARD_UNAVAILABLE') from exc
    mode = attempt_dir.stat().st_mode
    if not stat.S_ISDIR(mode) or mode & 0o077:
        raise DirectAPIHold('ATTEMPT_GUARD_PERMISSIONS_UNSAFE')
    # V2 files are separate from immutable V1 attempt markers.
    v2 = attempt_dir / 'EXPLICIT_USER_CLICKS_V2'
    if v2.is_symlink():
        raise DirectAPIHold('ATTEMPT_GUARD_SYMLINK')
    v2.mkdir(mode=0o700, exist_ok=True)
    if not stat.S_ISDIR(v2.stat().st_mode) or v2.stat().st_mode & 0o077:
        raise DirectAPIHold('ATTEMPT_GUARD_PERMISSIONS_UNSAFE')
    identity = (candidate['input_sha256'] + '\n' + candidate['family'] +
                '\n' + str(candidate['final_rank']) + '\n' + candidate['rbrc_id']).encode('utf-8')
    lock_path = v2 / ('inflight_' + sha(identity) + '.lock')
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    lock_fd = -1
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_mode & 0o077:
            raise DirectAPIHold('ATTEMPT_GUARD_PERMISSIONS_UNSAFE')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            raise DirectAPIHold('DUPLICATE_API_ATTEMPT_NO_AUTO_RETRY') from exc
        attempt_id = sha(identity + b'\n' + secrets.token_bytes(32))
        audit_path = v2 / ('attempt_' + attempt_id + '.jsonl')
        created = datetime.now(timezone.utc).isoformat()
        details = {
            'version': 'EXPLICIT_CLICK_V2', 'attempt_id': attempt_id,
            'input_sha256': candidate['input_sha256'],
            'family': candidate['family'], 'rank': candidate['final_rank'],
            'rbrc_id': candidate['rbrc_id'], 'created_utc': created,
            'event': 'user_click_reserved', 'note': 'not proof of provider sending',
        }
        audit_fd = os.open(audit_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                           getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            os.write(audit_fd, (json.dumps(details,sort_keys=True)+'\n').encode('utf-8'))
            os.fsync(audit_fd)
            try:
                yield attempt_id
            except BaseException as exc:
                # Record metadata only. Audit failure must not replace the original error.
                event = {'event': 'function_exited_with_exception',
                         'exception_type': type(exc).__name__,
                         'time_utc': datetime.now(timezone.utc).isoformat(),
                         'note': 'provider request status may be unknown'}
                try:
                    os.write(audit_fd, (json.dumps(event,sort_keys=True)+'\n').encode('utf-8'))
                    os.fsync(audit_fd)
                except OSError:
                    pass
                raise
            else:
                # Do not convert a successful (possibly billed) response into an error
                # solely because the optional final audit annotation failed.
                event = {'event': 'function_completed',
                         'time_utc': datetime.now(timezone.utc).isoformat(),
                         'note': 'local pipeline returned; not independent provider audit'}
                try:
                    os.write(audit_fd, (json.dumps(event,sort_keys=True)+'\n').encode('utf-8'))
                    os.fsync(audit_fd)
                except OSError:
                    pass
        finally:
            os.close(audit_fd)
    finally:
        if lock_fd >= 0:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def _v104_normalize_verified_short_train_rows(content, input_pairs):
    """Normalize short TRAIN row labels only after exact input source-edge proof.

    Example: FROZEN_TRAIN行35830、895、14418 -> ...35830、0895、14418.
    This only adds a leading zero to an integer rendering. The pinned V10
    citation validator already treats 0895 as row number 895, and independently
    checks all claimed rows against this uploaded evidence. Missing or mismatched
    evidence => NO normalization, original source-review HOLD is preserved.
    """
    import re as _re
    if not isinstance(content, str) or not isinstance(input_pairs, (tuple, list)):
        return content, ()
    known = {}
    for file_name, raw in input_pairs:
        if not isinstance(raw, bytes):
            continue
        try:
            obj = json.loads(raw.decode('utf-8-sig'))
            bundle = obj.get('evidence_bundle', {})
            train = bundle.get('provenance', {}).get('frozen_train', {}).get('sha256', '')
            if not isinstance(train, str) or not _re.fullmatch(r'[0-9a-fA-F]{64}', train):
                continue
            for role, edges in bundle.get('source_edges', {}).items():
                if not isinstance(edges, list):
                    continue
                for edge in edges:
                    if not isinstance(edge, dict) or edge.get('source_id') != 'FROZEN_TRAIN':
                        continue
                    number = edge.get('source_row_number')
                    if type(number) is int and number > 0:
                        known.setdefault(train.lower(), set()).add(number)
        except (ValueError, UnicodeError, AttributeError, TypeError):
            continue
    if not known:
        return content, ()
    pattern = _re.compile(r'\[8504:([0-9a-fA-F]{64})\s*/\s*FROZEN_TRAIN行'
                          r'([0-9]{1,8}(?:\s*[、,，]\s*[0-9]{1,8})+)\]')
    changes = []
    def replace(match):
        digest, label = match.group(1).lower(), match.group(2)
        values = [int(x) for x in _re.split(r'\s*[、,，]\s*', label)]
        if not (values and any(0 < n < 1000 for n in values)):
            return match.group(0)
        if len(values) > 100 or any(n not in known.get(digest, ()) for n in values):
            return match.group(0)
        # Keep all integer values. Never pad an unknown row or a wrong digest.
        normalized = '、'.join(str(n).zfill(4) for n in values)
        corrected = '[8504:' + digest + ' / FROZEN_TRAIN行' + normalized + ']'
        if corrected != match.group(0):
            changes.append({'kind': 'VERIFIED_TRAIN_ROW_LABEL_ZERO_PADDING',
                            'rows': values, 'original': match.group(0),
                            'normalized': corrected})
        return corrected
    result = pattern.sub(replace, content)
    return result, tuple(changes)



def run_one_via_8510_original(*, bundle: Mapping[str, Any], input_bytes: bytes,
                              api_key: str, consent: bool, scope_note: str = '',
                              stage3_dir: Path | None = None,
                              attempt_dir: Path | None = None,
                              client_factory: Callable[..., Any] | None = None,
                              public_lookup: Callable[..., dict] | None = None) -> dict:
    """Invoke the original V10 pipeline, at most one paid call, only after 3 gates.

    This wrapper does not implement 8510 parsing, prompt writing, public annotation,
    citation checks, or formatting. All five come from the pinned 8510 V10 source.
    The factory and lookup overrides exist for offline unit tests only.
    """
    phase = 'GATE_CHECK'
    try:
        if os.environ.get('STAGE4C_PAID_API_ENABLED', '') != ENABLE_VALUE:
            raise DirectAPIHold('PAID_API_LOCKED_BY_DEFAULT')
        if consent is not True:
            raise DirectAPIHold('EXPLICIT_SINGLE_CALL_CONSENT_REQUIRED')
        if not isinstance(api_key, str) or not api_key.strip():
            raise DirectAPIHold('BYOK_REQUIRED_FOR_THIS_SESSION')
        if type(scope_note) is not str or len(scope_note) > MAX_SCOPE_CHARS:
            raise DirectAPIHold('INVALID_SCOPE_NOTE')
        phase = 'PREPARE_INPUT'
        context = prepare_selected(bundle, input_bytes, stage3_dir=stage3_dir, scope_note=scope_note)
        candidate = context['candidate']
        shared = context['shared']
        # Before any external public lookup and model client instantiation.
        phase = 'ATTEMPT_GUARD'
        with _reserve_user_click(candidate, scope_note,
                                 Path(attempt_dir) if attempt_dir is not None else ATTEMPT_DIR) as attempt_id:
            # V10 original public-lookup implementation, no invented source references.
            phase = 'PUBLIC_LOOKUP'
            lookup = public_lookup if public_lookup is not None else shared.core.public_lookup.lookup_public_biology
            public_context = lookup(context['pairs'])
            phase = 'PROMPT_BUILD'
            messages = shared.core.build_messages(
                shared.core.receive_files(context['pairs'])[1], [], scope_note, public_context)
            user_content = messages[1]['content']
            source_text = user_content if isinstance(user_content, str) else user_content[0]['text']
            phase = 'SOURCE_SIZE_GATE'
            if len(source_text.encode('utf-8')) > shared.core.MAX_API_SOURCE_UTF8_BYTES + 60_000:
                raise DirectAPIHold('PUBLIC_CONTEXT_EXCEEDS_FULL_SOURCE_BOUND')
            phase = 'CLIENT_CONSTRUCT'
            if client_factory is None:
                from openai import OpenAI
                client_factory = OpenAI
            client = client_factory(api_key=api_key, max_retries=0)
            # Original 8510 V10 Chat Completions call signature, no model replacement.
            phase = 'PROVIDER_REQUEST'
            answer = client.chat.completions.create(
                service_tier='default', model=MODEL, timeout=600, messages=messages)
            phase = 'PROVIDER_RESPONSE'
            content = (answer.choices[0].message.content or '').strip()
            if not content:
                raise DirectAPIHold('EMPTY_PROVIDER_ANSWER_NO_AUTO_RETRY')
            phase = 'QUALITY_SCREEN'
            # Format-only repair for 1-3 digit TRAIN row numbers, after the real
            # uploaded 8504 evidence proves every row and its frozen TRAIN digest.
            # The byte-pinned V10 validator then rechecks the corrected text.
            content, citation_repairs = _v104_normalize_verified_short_train_rows(content, context['pairs'])
            quality = shared.quality_screen(content, public_context, context['records'], context['pairs'])
            if citation_repairs:
                quality['citation_syntax_normalization'] = {
                    'kind': 'VERIFIED_SHORT_TRAIN_ROW_LABEL_ONLY',
                    'count': len(citation_repairs),
                    'details': list(citation_repairs),
                    'input_source_edges_verified': True,
                    'original_train_file_byte_check': 'NOT_ASSESSED',
                    'scientific_validation': False,
                    'note': 'Only leading zeros added to numeric row labels; no scientific claims changed.',
                }
            phase = 'SERIALIZE_RESULT'
            md, raw, stamp = shared.format_response(
                context['records'], content, context['coverage'],
                public_context=public_context, quality=quality)
            return {'status': 'STAGE4C_LOCAL_8510_LLM_PROVISIONAL_NOT_SCIENTIFIC_VALIDATION',
                    'candidate': candidate, 'input_sha256': candidate['input_sha256'],
                    'attempt_id': attempt_id, 'model': MODEL, 'api_calls': 1,
                    'retry_count': 0, 'api_key_exported': False,
                    'scientific_validation': 'NOT_PERFORMED',
                    'formal_evidence_mutated': False, 'ranking_mutated': False,
                    'interpretation_text': content, 'quality': quality,
                    'markdown': md.decode('utf-8') if isinstance(md, bytes) else md,
                    'json': raw.decode('utf-8') if isinstance(raw, bytes) else raw,
                    'timestamp': stamp}
    except Exception as exc:
        raise Stage4EPhaseHold(phase, _stage4e_safe_class(exc)) from None


def render_stage4e_ui(*, streamlit_module: Any, bundle: Mapping[str, Any],
                      input_bytes: bytes, stage3_dir: Path | None = None) -> None:
    """User click is mandatory; default launcher locks all billable API activity."""
    st = streamlit_module
    st.caption('V14 4: 8504 locally reuses pinned 8510 V10 functions. Docker/Colima is NOT used.')
    st.warning('Provisional LLM interpretations are NOT scientific validation or KGE rank explanations.')
    st.caption('Past attempt retained. Only a fresh user click sends a new request; each may be billed. No automatic retry.')
    try:
        current = prepare_selected(bundle, input_bytes, stage3_dir=stage3_dir)
    except Exception as exc:
        st.error('STAGE4C_SOURCE_HOLD: ' + type(exc).__name__)
        return
    st.json(safe_preview(current))
    live_allowed = os.getenv('STAGE4C_PAID_API_ENABLED') == ENABLE_VALUE
    if not live_allowed:
        st.info('API_LOCKED: this isolated launcher forbids paid API calls. No Colima SSD required.')
    st.caption('BYOK Status: use Save BYOK before Run. Saved means this 8504 Streamlit session only; no API key is written to files or exported. The existing 8510 container key is not accessed.')
    # Keep the credential in Streamlit server-side session memory, not files.
    # This copy survives widget removal on a Streamlit rerun; never auto-sends.
    if 'stage4c_ephemeral_key' not in st.session_state:
        st.session_state['stage4c_ephemeral_key'] = st.session_state.get('stage4c_saved_session_key', '')
    with st.form('stage4c_one_request_form', clear_on_submit=False):
        scope = st.text_input('Additional instruction (optional)', max_chars=MAX_SCOPE_CHARS,
                              key='stage4c_scope')
        key = st.text_input('OpenAI BYOK (required only for separately approved live call)',
                            type='password', key='stage4c_ephemeral_key')
        consent = st.checkbox('I approve sending this exact candidate input and identifiers to public sources and one paid LLM API call',
                              key='stage4c_explicit_one_call_consent')
        save_key = st.form_submit_button('Save BYOK for this session')
        submitted = st.form_submit_button('Run LLM interpretation once',
                                          disabled=not live_allowed)
    if save_key:
        if isinstance(key, str) and key.strip():
            st.session_state['stage4c_saved_session_key'] = key.strip()
        else:
            st.session_state.pop('stage4c_saved_session_key', None)
            st.error('BYOK_REQUIRED: no key was saved; no API request was made.')
    saved_key = st.session_state.get('stage4c_saved_session_key', '')
    saved = bool(saved_key) and saved_key == key
    if saved:
        st.success('BYOK Status: saved (8504 current Streamlit session only)')
    else:
        st.info('BYOK Status: not saved. Enter key and click Save BYOK for this session.')
    if submitted and not saved:
        st.error('BYOK_NOT_SAVED_FOR_THIS_SESSION; NO_API_REQUEST')
    elif submitted:
        try:
            out = run_one_via_8510_original(bundle=bundle, input_bytes=input_bytes,
                   api_key=key, consent=consent, scope_note=scope, stage3_dir=stage3_dir)
        except Stage4EPhaseHold as hold:
            st.error('STAGE4E_EXECUTION_HOLD_NO_AUTO_RETRY: PHASE=' + hold.phase
                     + '; CLASS=' + hold.category + '; NO_AUTO_RESEND')
        except Exception:
            st.error('STAGE4E_EXECUTION_HOLD_NO_AUTO_RETRY: PHASE=UNCLASSIFIED; CLASS=OTHER_EXCEPTION')
        else:
            st.session_state['stage4c_local_result'] = (out['input_sha256'], out)
    state = st.session_state.get('stage4c_local_result')
    if state and state[0] == current['input_sha256']:
        out = state[1]
        st.subheader('8510 provisional LLM interpretation - not reviewed')
        st.markdown(out['interpretation_text'])
        st.json(out['quality'])
        selected = current['candidate']
        download_base = ('8510_PROVISIONAL__' + selected['disease_iri'].rsplit('/', 1)[-1]
                         + '__' + selected['family'] + '__rank' + str(selected['final_rank'])
                         + '__' + selected['rbrc_id'] + '__gpt-6-luna__' + out['timestamp']
                         + '__input' + selected['input_sha256'][:12]
                         + '__out' + sha(out['json'].encode('utf-8'))[:10])
        st.download_button('Download Markdown', data=out['markdown'],
                           file_name=download_base+'.md',
                           mime='text/markdown', key='stage4c_md')
        st.download_button('Download JSON', data=out['json'],
                           file_name=download_base+'.json',
                           mime='application/json', key='stage4c_json')
        st.caption('No automatic promotion to KGE ranking / F/HML / G4; reference URLs require review.')
        render_stage5_controls(st=st, out=out, current=current)

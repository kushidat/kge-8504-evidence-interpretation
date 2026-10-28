"""Tests for v1.0.2 changed behavior only.  No frozen research sources read."""
import importlib
import re
from datetime import datetime, timezone
import json
import sys
import types
from pathlib import Path
from hashlib import sha256
import io
import pandas as pd
import pytest

APP = Path(__file__).resolve().parent / 'app'
if not APP.is_dir():
    APP = Path(__file__).resolve().parent.parent / 'app'
assert APP.is_dir(), 'Missing nearby app/ folder'
sys.path.insert(0, str(APP))
a = importlib.import_module('kge_evidence_bundle_readonly_v1_0_2')
CASES = (
    ('MONDO_0005148','RBRC-GSC0231'),
    ('MONDO_0004976','RBRC06467'),
    ('MONDO_0005105','RBRC02937'),
)

@pytest.mark.parametrize('disease,mouse',CASES)
def test_selected_disease_never_uses_archived_single_case(disease,mouse):
    d=f'http://purl.obolibrary.org/obo/{disease}'
    hist=a.historical_sparql_llm_consensus(d,mouse)
    ext=a.candidate_specific_external_evidence(d,mouse)
    provisional=a.derive_provisional_assessment(ext)
    assert hist['selected_disease_iri'] == d
    assert hist['selected_rbrc_id'] == mouse
    assert hist['status'] == 'NOT_CONNECTED_EQUAL_SCOPE_SPARQL_LLM'
    assert hist['records'] == []
    assert hist['candidate_specific_claim'] is False
    assert ext['status'] == 'NOT_CONNECTED_CANDIDATE_SPECIFIC_SOURCES'
    assert ext['candidate_specific_claim'] is False
    assert provisional['status'] == 'NOT_ASSESSED'
    assert provisional['proposed_f_class'] == 'Not assessed'
    assert provisional['proposed_hml'] == 'Not assessed'
    assert provisional['evidence_basis'] == []


def test_builder_wiring_of_generic_evidence_source_without_research_access(monkeypatch):
    """Only changed wiring is mocked; does NOT validate actual biological sources."""
    monkeypatch.setattr(a,'assert_live_ranking_authority',lambda **k: None)
    monkeypatch.setattr(a,'validate_receipt',lambda **k:{'status':'OFFICIAL_8504_PINNED_LOADER_SELECTED_ROW_VERIFIED'})
    monkeypatch.setattr(a,'load_frozen_train',lambda:(pd.DataFrame({'s':[],'p':[],'o':[]}),{'sha256':'stubbed'}))
    keys=('mouse_gene_edges','mouse_mp_edges','mouse_go_edges','gene_disease_edges','orthology_edges','human_gene_disease_edges','hp_mp_edges','disease_hp_edges','direct_gene_paths','ortholog_gene_paths','phenotype_paths')
    monkeypatch.setattr(a,'derive_train_evidence',lambda *args:{**{k:[] for k in keys},'train_go_keys':set()})
    monkeypatch.setattr(a,'go_evidence_for_mouse',lambda *args:([], {'source':'mock'}))
    monkeypatch.setattr(a,'disease_gene_context_from_train',lambda *args:{'gene_ids':[],'gene_disease_edges':[]})
    monkeypatch.setattr(a,'load_go_summary_verified',lambda:(pd.DataFrame(),{}))
    monkeypatch.setattr(a,'derive_disease_gene_go_context',lambda *args:{'disease_gene_count':0,'disease_gene_linked_go_count':0,'candidate_go_count':0,'shared_go_count':0,'shared_candidate_disease_gene_go':[]})
    monkeypatch.setattr(a,'bind_live_evidence_bundle',lambda **k: None)
    for disease,mouse in CASES:
        d=f'http://purl.obolibrary.org/obo/{disease}'
        m=f'http://metadb.riken.jp/db/rikenbrc_mouse/{mouse}'
        bundle=a.build_evidence_bundle(disease_iri=d,mouse_iri=m,
            ranking={'family':'node2vec','final_rank':1},ranking_verification_receipt={},trusted_ranking_authority=None)
        assert bundle['identity']['disease_iri']==d
        assert bundle['identity']['rbrc_id']==mouse
        assert bundle['ranking']['frozen_flag'] is True  # mocked prior gate, NOT real verification
        assert bundle['historical_sparql_llm_evidence']['status']=='NOT_CONNECTED_EQUAL_SCOPE_SPARQL_LLM'
        assert bundle['strain_and_allele']['candidate_specific_claim'] is False
        assert bundle['assessment']['formal_assessment_boundary']['hml']=='Not assessed'
        assert bundle['assessment']['provisional_assessment']['proposed_hml']=='Not assessed'
        assert bundle['external_papers']['records']==[]
        assert bundle['provenance']['primary_test_access'] is False


def load_wrapper_with_stub_streamlit(monkeypatch):
    st=types.ModuleType('streamlit')
    st.dataframe=lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules,'streamlit',st)
    sys.modules.pop('streamlit_app_8504_v1_0_2_emergency_scope_correction',None)
    b=importlib.import_module('streamlit_app_8504_v1_0_2_emergency_scope_correction')
    return b


def test_top50_csv_contract_and_scope_no_full_rank_export(monkeypatch):
    b=load_wrapper_with_stub_streamlit(monkeypatch)
    n=5892
    frame=pd.DataFrame({'final_rank':[str(i) for i in range(n,0,-1)], 'mouse_iri':[f'fake:{i}' for i in range(n)]})
    loaded={'frames':{'node2vec':frame}}
    raw=b.top50_csv_from_verified_frame(loaded,'node2vec')
    parsed=pd.read_csv(io.BytesIO(raw))
    assert len(parsed)==50
    assert parsed.final_rank.tolist()==list(range(1,51))
    assert raw.startswith(b'\xef\xbb\xbf')
    assert list(frame['final_rank'])==[str(i) for i in range(n,0,-1)]
    with pytest.raises(RuntimeError,match='TOP50_CONTRACT_FAILED'):
        b.top50_csv_from_verified_frame({'frames':{'node2vec':frame.loc[frame['final_rank'].astype(int) > 50]}},'node2vec')


def test_new_prompt_and_no_pinned_case_in_runtime(tmp_path):
    prompt=(APP/'LLM_PROVISIONAL_PROMPT_V1_0_2_20261028.txt').read_bytes()
    assert b'T2D' not in prompt and b'GSC0231' not in prompt
    assert sha256(prompt).hexdigest()=='e62fe1f1a5bbfee56f4cc791c408958eaf7a874bad182373239d3acbfae08284'
    for fn in ['kge_evidence_bundle_readonly_v1_0_2.py','streamlit_app_8504_v1_0_2_emergency_scope_correction.py']:
        txt=(APP/fn).read_text()
        assert 'HISTORICAL_SPARQL_LLM_FILES' not in txt
        assert 'CANDIDATE_SNAPSHOT_PATH' not in txt
        assert 'CONSENSUS_7_OF_7' not in txt
        assert 'MONDO_0005148' not in txt
        assert 'RBRC-GSC0231' not in txt
    assert 'LLM_CALL=NO' in (APP/'streamlit_app_8504_v1_0_2_emergency_scope_correction.py').read_text()

class FakeUI:
    def __init__(self):
        self.events=[]
        self.session_state={}
        self.sidebar=self
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def _log(self,name,*args,**kwargs):
        self.events.append((name,args,kwargs))
    def __getattr__(self,name):
        if name in {'spinner','expander'}: return lambda *a,**kw: self
        if name=='tabs': return lambda labels:[self for _ in labels]
        if name=='columns': return lambda n: [self for _ in range(n if isinstance(n,int) else len(n))]
        if name=='selectbox': return lambda label,options,**kw: options[0]
        if name=='number_input': return lambda label,**kw: kw.get('value',1)
        if name=='file_uploader': return lambda *a,**kw: None
        if name=='stop': return lambda : (_ for _ in ()).throw(AssertionError('unexpected st.stop'))
        return lambda *args,**kwargs: self._log(name,*args,**kwargs)


@pytest.mark.parametrize('disease,mouse',CASES)
def test_ui_displays_generic_scope_and_no_historical_consensus(monkeypatch,disease,mouse):
    b=load_wrapper_with_stub_streamlit(monkeypatch)
    fake=FakeUI()
    fake.session_state['fx9b_active_audit_query']=disease
    b.st=fake
    def mock_loaded(d):
        assert d==disease
        n=5892
        frame=pd.DataFrame({'final_rank':list(range(1,n+1)),
                            'mouse_iri':[f'http://metadb.riken.jp/db/rikenbrc_mouse/RBRC{i:05d}' for i in range(n)]})
        return {'disease_iri':f'http://purl.obolibrary.org/obo/{disease}','frames':{'node2vec':frame}}
    helper=types.SimpleNamespace(normalize_mondo_id=lambda d:d,load_all_six_family_frames=mock_loaded)
    base=types.SimpleNamespace(verified_helper=lambda :helper,FAMILIES=('node2vec',),MOUSE_N=5892)
    monkeypatch.setattr(b,'verify_official_loaded_row_trusted',lambda **kw: (
        {'family':'node2vec','final_rank':1},{'mouse_iri':f'http://metadb.riken.jp/db/rikenbrc_mouse/{mouse}'},object()))
    bundle={
        'identity':{'disease_iri':f'http://purl.obolibrary.org/obo/{disease}',
                    'mouse_iri':f'http://metadb.riken.jp/db/rikenbrc_mouse/{mouse}',
                    'rbrc_id':mouse},
        'ranking':{'family':'node2vec','final_rank':1},
        'go_context':{'disease_gene_count':0,'candidate_go_count':0,
                    'disease_gene_linked_go_count':0,'shared_go_count':0,
                    'shared_candidate_disease_gene_go':[],'candidate_mouse_go':[]},
        'unproven_scope':[],
        'source_edges':{'candidate_intrinsic':[],'candidate_linking':[],'disease_context':[]},
        'structural_paths':[],
        'historical_sparql_llm_evidence':a.historical_sparql_llm_consensus(f'http://purl.obolibrary.org/obo/{disease}',mouse),
        'strain_and_allele':{'candidate_specific_claim':False},
        'external_papers':{'records':[]},
        'assessment':{'formal_assessment_boundary':{'f_class':'Not assessed','hml':'Not assessed','review_status':'unreviewed'},
            'provisional_assessment':a.derive_provisional_assessment({}),
            'stock_phenotype':'NOT_ASSESSED','source_independence':'NOT_ESTABLISHED','llm_provisional_status':'NOT_RUN','rules':[]},
        'provenance':{},
    }
    monkeypatch.setattr(b,'build_evidence_bundle',lambda **kw: bundle)
    b.render_evidence_panel(base)
    text='\n'.join(str(args) for name,args,kwargs in fake.events if name in ('info','caption','warning','success','header','metric'))
    assert '未実装・未接続' in text
    assert '2型糖尿病' not in text
    assert 'CONSENSUS_7_OF_7' not in text
    assert any(name=='download_button' and re.fullmatch(rf'KGE_8504_{disease}_node2vec_TOP50_[0-9]{{8}}_[0-9]{{6}}_JST\.csv', kw.get('file_name',''))
               for name,args,kw in fake.events)
    assert len([e for e in fake.events if e[0]=='download_button'])>=5


def test_export_filename_time_zone_and_no_rank_change(monkeypatch):
    b=load_wrapper_with_stub_streamlit(monkeypatch)
    fixed=datetime(2026,10,28,10,16,30,tzinfo=timezone.utc)
    assert b.top50_export_filename('MONDO_0004976','node2vec',fixed)==(
        'KGE_8504_MONDO_0004976_node2vec_TOP50_20261028_191630_JST.csv')
    assert b.top50_export_filename('MONDO_0005148','ComplEx',fixed)==(
        'KGE_8504_MONDO_0005148_ComplEx_TOP50_20261028_191630_JST.csv')
    with pytest.raises(ValueError,match='TIMEZONE_AWARE'):
        b.top50_export_filename('MONDO_0005148','node2vec',datetime(2026,10,28,19,16,30))
    with pytest.raises(ValueError,match='INVALID_DISEASE'):
        b.top50_export_filename('../../other','node2vec',fixed)
    with pytest.raises(ValueError,match='INVALID_FAMILY'):
        b.top50_export_filename('MONDO_0005148','../../temp',fixed)


def test_no_stale_single_case_f3_medium_in_llm_tab(monkeypatch):
    b=load_wrapper_with_stub_streamlit(monkeypatch)
    source=(APP/'streamlit_app_8504_v1_0_2_emergency_scope_correction.py').read_text()
    assert 'F3/Medium' not in source
    assert 'top50_export_filename(disease_id, family)' in source

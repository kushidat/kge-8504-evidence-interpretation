#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only scientific next-step panel for a KGE 8504 V0.6 Evidence Bundle.

This module does not validate or designate disease models. It does not perform
training, score reconstruction, SPARQL, API calls or external retrieval.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
import json
import os
import re

EXTENSION_ID = "KGE_8504_RESEARCH_NEXT_STEPS_ISOLATED_V0_7_20261025"
FAMILY_FOUR = {"TransE", "RotatE", "ComplEx", "CompGCN"}
FAMILY_ALL = FAMILY_FOUR | {"node2vec", "RDF2Vec"}
MAX_PAYLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_FILENAME = "EVIDENCE_LLM_INPUT__MONDO_0005148__node2vec__rank1__RBRC-GSC0231.json"


class EvidenceContractError(ValueError):
    """Unsupported, ambiguous or unsafe Evidence Bundle."""


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_int(value: Any, default: int = -1) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _iri_tail(v: str) -> str:
    return _safe_string(v).split("/")[-1]


def _compact_source_edge(edge: Mapping[str, Any]) -> str:
    src = _safe_string(edge.get("source_id"))
    row = _as_int(edge.get("source_row_number"))
    if src and row >= 0:
        return f"{src}:ROW:{row}"
    return ""


def evidence_payload_to_bundle(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise EvidenceContractError("Evidence入力はJSONオブジェクトである必要があります")
    if "evidence_bundle" in payload:
        obj = payload["evidence_bundle"]
    else:
        obj = payload
    if not isinstance(obj, dict):
        raise EvidenceContractError("evidence_bundleがオブジェクトではありません")
    b = deepcopy(obj)
    ident = as_mapping(b.get("identity"))
    ranking = as_mapping(b.get("ranking"))
    for field in ("disease_iri", "mouse_iri"):
        iri = ident.get(field)
        if not isinstance(iri, str) or not re.match(r"^https?://\S+$", iri):
            raise EvidenceContractError(f"identity.{field}には絶対IRIが必要です")
    if ranking:
        if ranking.get("frozen_flag") is not True:
            raise EvidenceContractError("凍結順位の確認に失敗しました (frozen_flag)")
        if not isinstance(ranking.get("family"), str) or not ranking["family"]:
            raise EvidenceContractError("ranking.familyが不足しています")
        if _as_int(ranking.get("final_rank")) < 1:
            raise EvidenceContractError("ranking.final_rankが不正です")
    for field in ("primary_test_access", "test_access", "withheld_access", "training", "ranking_mutation"):
        if as_mapping(b.get("provenance")).get(field) is True:
            raise EvidenceContractError(f"隔離境界違反：provenance.{field}=true")
    return b


def read_json_readonly(path: Path) -> Tuple[Dict[str, Any], str]:
    path = Path(path).expanduser()
    if not path.is_file():
        raise EvidenceContractError(f"Evidence JSONがありません: {path}")
    if path.stat().st_size > MAX_PAYLOAD_BYTES:
        raise EvidenceContractError("Evidence JSONが10MBを超えています")
    data = path.read_bytes()
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceContractError("Evidence JSONの読取に失敗しました") from exc
    return evidence_payload_to_bundle(payload), sha256(data).hexdigest()


def _edge_types(bundle: Mapping[str, Any], kind: str) -> List[Mapping[str, Any]]:
    edges = as_mapping(bundle.get("source_edges"))
    return [e for e in as_list(edges.get(kind)) if isinstance(e, dict)]


def _go_statistics(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    go = as_mapping(bundle.get("go_context"))
    mouse_terms = [g for g in as_list(go.get("candidate_mouse_go")) if isinstance(g, dict)]
    disease_terms = [g for g in as_list(go.get("disease_gene_linked_go")) if isinstance(g, dict)]
    shared = [g for g in as_list(go.get("shared_candidate_disease_gene_go")) if isinstance(g, dict)]
    train_set = {(g.get("go_iri"), g.get("aspect")) for g in mouse_terms if g.get("in_frozen_train_mouse_go") is True}
    # Candidate-linked human gene identifiers come from explicit orthology edges,
    # never inferred from a free-text label or post-hoc GO intersection.
    candidate_gene_ids = {
        _iri_tail(str(edge.get("object_iri")))
        for edge in _edge_types(bundle, "candidate_linking")
        if edge.get("evidence_type") == "FROZEN_TRAIN_ORTHOLOGY" and edge.get("object_iri")
    }
    hist_gene = as_mapping(as_mapping(bundle.get("historical_sparql_llm_evidence")).get("group_gene_context"))
    gene_label = (str(hist_gene.get("gene_symbol")) if len(candidate_gene_ids) == 1
                  and str(hist_gene.get("human_gene_id")) in candidate_gene_ids
                  and hist_gene.get("gene_symbol") else "候補に関連付くヒト疾患Gene")
    groups = Counter()
    same_evidence = 0
    freq = []
    for g in shared:
        genes = {v for v in _safe_string(g.get("disease_gene_ids_matched")).split("|") if v}
        if not candidate_gene_ids or not genes:
            groups["比較遺伝子未照合"] += 1
        elif genes & candidate_gene_ids:
            groups["候補関連Geneのみ"] += 1 if genes.issubset(candidate_gene_ids) else 0
            groups["候補関連Geneと他Gene"] += 1 if not genes.issubset(candidate_gene_ids) else 0
        else:
            groups["候補関連Gene以外のみ"] += 1
        if (g.get("candidate_mouse_references") == g.get("disease_context_references") and
            g.get("candidate_mouse_evidence_codes") == g.get("disease_context_evidence_codes")):
            same_evidence += 1
        n = _as_int(g.get("mouse_count_for_go_term_in_summary"))
        if n >= 0:
            freq.append(n)
    shared_train = sum((g.get("go_iri"), g.get("aspect")) in train_set for g in shared)
    return {
        "candidate_go_count": len(mouse_terms),
        "disease_gene_linked_go_count": len(disease_terms),
        "shared_exact_go_count": len(shared),
        "candidate_linked_human_gene_ids": sorted(candidate_gene_ids),
        "candidate_linked_gene_label": gene_label,
        "candidate_gene_only_shared_go": groups["候補関連Geneのみ"],
        "candidate_gene_and_other_shared_go": groups["候補関連Geneと他Gene"],
        "other_gene_only_shared_go": groups["候補関連Gene以外のみ"],
        "unclassified_shared_go": groups["比較遺伝子未照合"],
        "shared_go_mouse_train_direct_count": shared_train,
        "shared_go_mouse_not_train_direct_count": len(shared) - shared_train,
        "shared_same_evidence_code_and_reference_count": same_evidence,
        "go_term_mouse_counts": sorted(freq),
        "analysis_status": "POSTHOC_CONTEXT_NOT_RANK_CAUSALITY",
        "completeness": "GO_CONTEXT_PRESENT" if go else "GO_CONTEXT_ABSENT",
    }


def _has_verified_sparql_result(bundle: Mapping[str, Any]) -> Optional[bool]:
    # Historical matched-Mouse membership is never an equal-scope SPARQL result.
    retrieval = as_mapping(bundle.get("retrieval"))
    v = retrieval.get("sparql_candidate_verified")
    # Equal-snapshot / equal-disease SPARQL provenance is mandatory to show YES/NO.
    if (not isinstance(v, bool) or
        retrieval.get("sparql_disease_iri") != as_mapping(bundle.get("identity")).get("disease_iri") or
        not re.fullmatch(r"[0-9a-f]{64}", str(retrieval.get("sparql_query_sha256", ""))) or
        not isinstance(retrieval.get("sparql_snapshot_id"), str) or
        not retrieval.get("sparql_snapshot_id")):
        return None
    return v


def _new_q(question_id: str, title: str, observation: str, needed: List[str],
           method: List[str], possible_interpretation: str, boundary: str,
           evidence_refs: List[str]) -> Dict[str, Any]:
    return {"question_id": question_id, "title": title, "status": "未検証",
            "observed_basis": observation, "required_data": needed,
            "verification_method": method, "possible_interpretation": possible_interpretation,
            "interpretation_limit": boundary,
            "evidence_refs": sorted({r for r in evidence_refs if r})}


def make_next_steps(payload: Mapping[str, Any], payload_sha256: Optional[str] = None) -> Dict[str, Any]:
    """Deterministic, non-LLM, source-bounded research suggestions.

    No biological model decision and no predicted causal rank contributions.
    """
    b = evidence_payload_to_bundle(payload)
    identity = as_mapping(b["identity"])
    ranking = as_mapping(b.get("ranking"))
    edges = as_mapping(b.get("source_edges"))
    assessment = as_mapping(b.get("assessment"))
    provenance = as_mapping(b.get("provenance"))
    mouse_iri = identity["mouse_iri"]
    disease_iri = identity["disease_iri"]
    family = ranking.get("family") or ("SPARQL" if "SPARQL" in _safe_string(identity.get("retrieval_source")).upper() else "NOT_SUPPLIED")
    rank = _as_int(ranking.get("final_rank")) if ranking else None
    candidate = identity.get("rbrc_id") or _iri_tail(mouse_iri)

    intrinsic = _edge_types(b, "candidate_intrinsic")
    linking = _edge_types(b, "candidate_linking")
    mouse_gene = [x for x in intrinsic if x.get("evidence_type") == "FROZEN_TRAIN_MOUSE_GENE"]
    mouse_mp = [x for x in intrinsic if x.get("evidence_type") == "FROZEN_TRAIN_MOUSE_MP"]
    hp_mp = [x for x in linking if x.get("evidence_type") == "FROZEN_TRAIN_HP_MP"]
    mp_set = {x.get("object_iri") for x in mouse_mp if x.get("object_iri")}
    mapped_mp = {x.get("object_iri") for x in hp_mp if x.get("object_iri")}
    mp_intersection = sorted(mp_set & mapped_mp)

    go_stats = _go_statistics(b)
    structural_paths = [p for p in as_list(b.get("structural_paths")) if isinstance(p, dict)]
    hist = as_mapping(b.get("historical_sparql_llm_evidence"))
    allele = as_mapping(b.get("strain_and_allele"))
    papers = as_mapping(b.get("external_papers"))
    pheno = as_mapping(allele.get("phenotype"))
    allele_id = as_mapping(allele.get("allele_identity"))
    primary_paper_state = _safe_string(papers.get("primary_experimental_paper_status"))
    has_paper = primary_paper_state and primary_paper_state not in ("NOT_IDENTIFIED", "NOT_IDENTIFIED_AFTER_PROJECT_CHAT_AND_EXTERNAL_SOURCE_REVIEW")
    known_sparql = _has_verified_sparql_result(b)
    associated_gene_label = go_stats["candidate_linked_gene_label"]

    evidence_index = {}
    ranking_sha = ranking.get("family_ranking_sha256")
    if isinstance(ranking_sha, str) and len(ranking_sha) == 64:
        evidence_index["RANKING_SHA256:" + ranking_sha] = "凍結ランキング来歴"
    for collection in ("candidate_intrinsic", "candidate_linking", "disease_context"):
        for edge in _edge_types(b, collection):
            ref = _compact_source_edge(edge)
            if ref:
                evidence_index[ref] = "凍結KGの出典行"
    for p in structural_paths:
        for x in as_list(p.get("path_nodes")):
            if isinstance(x, str) and x.startswith("http"):
                evidence_index[x] = "構造的な経路のノード（因果寄与ではない）"
    go = as_mapping(b.get("go_context"))
    for g in as_list(go.get("shared_candidate_disease_gene_go")):
        if isinstance(g, dict) and isinstance(g.get("go_iri"), str):
            evidence_index[g["go_iri"]] = "候補と疾患関連遺伝子の共有GO"
    if allele_id.get("mgi_allele_id"):
        evidence_index[str(allele_id["mgi_allele_id"])] = "アレル記録"
    for record in as_list(papers.get("records")):
        if not isinstance(record, dict):
            continue
        for k in ("reference_id", "pmid", "doi"):
            if record.get(k):
                evidence_index[str(record[k])] = "候補関連資料（出典種別を要照合）"
    if pheno.get("phenotype_reference"):
        evidence_index[str(pheno["phenotype_reference"])] = "表現型記録の出典"
    for ref in (disease_iri, mouse_iri):
        evidence_index[ref] = "候補識別子"

    ranksource = "RANKING_SHA256:" + ranking_sha if isinstance(ranking_sha, str) and len(ranking_sha) == 64 else ""
    gene_refs = [_compact_source_edge(x) for x in mouse_gene + linking if x.get("evidence_type") in
                 {"FROZEN_TRAIN_MOUSE_GENE", "FROZEN_TRAIN_ORTHOLOGY", "FROZEN_TRAIN_HUMAN_GENE_DISEASE"}]
    mp_refs = [_compact_source_edge(x) for x in mouse_mp + hp_mp]
    go_refs = [g.get("go_iri") for g in as_list(go.get("shared_candidate_disease_gene_go")) if isinstance(g, dict)]

    questions = []
    if family == "node2vec":
        questions.append(_new_q(
            "KGE-RANK-COMPARE", "第1位を含む順位と類似度を同条件の候補で比較する",
            f"node2vecの凍結順位は{rank}位。node2vecは疾患とMouseの埋め込みの類似度で順位付けし、Gene/HP側のRRF内訳とは区別する。",
            ["同一疾患の凍結node2vec全Mouse（5,892候補）順位・コサイン類似度", f"{associated_gene_label}関連系統の同一版Mouse識別子と各順位", "ノード次数・接続成分・マウス側GO/MP辺数が近い対照候補"],
            ["凍結順位を再採点せずに、GCK関連候補と次数等を揃えた候補の類似度・順位を比較する", "類似度差をGene関連・MP関連・GO関連・接続成分別に記述し、対応関係の重複を明示する"],
            f"{associated_gene_label}関連候補の中でも相対的な上位提示が特異的か、共有するグラフ特徴で説明できそうかを絞り込める。",
            "これは相関的な比較であり、特定の辺・GO・経路が順位1位を引き起こした証明ではない。", [ranksource, disease_iri, mouse_iri]
        ))
        questions.append(_new_q(
            "KGE-WALKS", "凍結node2vec実ウォークで何が共起したかを確かめる",
            f"凍結Trainには候補のGene {len(mouse_gene)}辺・MP {len(mouse_mp)}辺と構造的経路 {len(structural_paths)}本の記録がある。",
            ["凍結node2vecのwalker設定・seed・実ウォーク列または再現可能な実行ログ", "候補と疾患の窓内共起数、経路上ノード共起数、対照候補の同値"],
            ["元walkerの方向/重み/逆辺契約を検証し、実ウォーク中の候補–マウスGene–ヒト疾患関連Gene–疾患に関係する共起を計測する", "同次数の対照系統の共起分布と比較する"],
            "候補と疾患がどの局所構造を通じて学習時に近づく機会を持ったかを調べられる。",
            "経路がKGに存在しても、その順序でウォークされた保証はない。ウォークの観測だけで順位への因果寄与は確定しない。", gene_refs + mp_refs
        ))
    elif family in FAMILY_FOUR:
        questions.append(_new_q(
            "KGE-RANK-COMPARE", "Gene・Phenotype別予測と最終RRF順位を比較する",
            f"{family}の凍結順位{rank}位。個別Gene/Phenotypeスコアの寄与はこのEvidence入力からは未測定。",
            ["疾患のGene/HP検索アンカーの固定リスト", "手法の各Gene/HPに対する全Mouse生スコア", "Gene・Phenotype別順位とRRF(k=60)の統合内訳"],
            ["原本のスコア方向と凍結RRF集約契約を照合して候補別寄与を計算", "同じGene/MP/GO特徴を持つ対照と比較し、順位の変動を原因と断定せず表示"],
            "どの予測アンカー側が候補の集約順位に大きな数値寄与を持つか調べられる。",
            "RRFの数値寄与は、生物学的証拠や学習した個別辺の因果効果と同一ではない。", [ranksource, disease_iri, mouse_iri]
        ))
    elif family == "RDF2Vec":
        questions.append(_new_q(
            "KGE-RANK-COMPARE", "凍結RDF2Vecの関係別prototypeと順位統合を追跡する",
            f"RDF2Vecの凍結順位{rank}位。node2vecと同じ単純な疾患–Mouseコサイン比較だと仮定しない。",
            ["凍結RDF2Vecウォーク設定・関係別prototype", "凍結scorerのGene/Phenotype別生スコア・統合ログ"],
            ["関係ラベル付きウォークとprototype、予測および統合過程を元のscorer契約で追跡", "近傍構造が似た系統を対照に比較"],
            "候補の順位形成と関係別予測がどこで結び付くかを説明できる可能性がある。",
            "個別ウォークやGOの存在から因果寄与を断定しない。", [ranksource, disease_iri, mouse_iri]
        ))
    else:
        questions.append(_new_q(
            "KGE-RANK-COMPARE", "候補を作成した探索経路と、その比較データを照合する",
            f"候補の探索手法は{family}。KGE専用の順位計算を仮定しない。",
            ["探索の種類と版", "同一疾患・同一版の比較対象候補", "検索query・Graph/資料の根拠"],
            ["SPARQLなら実検索経路と出典、KGEなら該当familyの凍結scorerを区別して比較する"],
            "現在提示されている候補がどの情報により列挙されたかを再現可能にできる。",
            "直接検索で列挙されたことは、候補のモデル採否判断とは異なる。", [disease_iri, mouse_iri]
        ))

    questions.append(_new_q(
        "KGE-EDGE-ABLATION", "Gene・MP・GO情報が順位へ寄与するか対照付きで検証する",
        f"候補の凍結TrainにGene {len(mouse_gene)}辺・MP {len(mouse_mp)}辺・GO {sum(x.get('evidence_type') == 'FROZEN_TRAIN_MOUSE_GO' for x in intrinsic)}辺が記録されている。",
        ["凍結TRAINの読み取り専用複製", "同手法・同候補集合・同設定の複数seedでの基準スコア", "除外する辺と同数・同relation・類似次数の対照辺集合"],
        ["Gene/MP/GOを種類別に除いた再学習と、対照辺除外の再学習を別々に実施", "候補の生スコア・順位差、seed間の平均差とばらつきを対照と比較"],
        "特定の情報群の削除による順位変化が対照を超えるなら、その情報群の寄与を支持できる。",
        "実験未実施。単純なKG経路表示や推論時の辺削除はこの検証の代わりにならない。primary_test・TESTは使わない。", gene_refs + mp_refs + go_refs[:3]
    ))

    if mouse_mp or hp_mp:
        eq = "、".join(_iri_tail(x) for x in mp_intersection) if mp_intersection else "記録上の完全一致なし"
        questions.append(_new_q(
            "PHENOTYPE-ALIGNMENT", "候補マウスで確認すべき疾患関連表現型を明示する",
            f"候補側MP={len(mp_set)}種類、疾患HP→MP対応={len(mapped_mp)}種類。表示中の両集合の完全一致：{eq}。",
            ["元のMP/HPラベル・階層関係・変換原本", "当該アレルの測定条件（背景・性別・週齢）と表現型の実測原本", "目的の疾患で研究者が重視する表現型（例：耐糖能・インスリン分泌）"],
            ["完全一致・階層的関連・明示された未照合を分ける", "高血糖記録とインスリン抵抗性等の未検証事項を並列に提示する"],
            "研究者が目的に合う追加表現型測定を選択できる。",
            "MPの完全一致がないことは疾患との無関係を意味せず、アプリが疾患モデルの採否を決める根拠にもならない。", mp_refs
        ))

    if as_mapping(b.get("go_context")):
        questions.append(_new_q(
            "GO-INDEPENDENCE", "GO一致が独立した証拠なのか同じ遺伝子情報の再提示か調べる",
            f"共有GO={go_stats['shared_exact_go_count']}種類。疾患側対応Geneが{associated_gene_label}のみ={go_stats['candidate_gene_only_shared_go']}、同Geneと他遺伝子={go_stats['candidate_gene_and_other_shared_go']}、別遺伝子のみ={go_stats['other_gene_only_shared_go']}、分類不能={go_stats['unclassified_shared_go']}。候補の凍結Trainで直接GO辺が確認できる共有GO={go_stats['shared_go_mouse_train_direct_count']}。",
            ["GO provenance/supportの原本行（Evidenceコード・PMID・遺伝子・species）", "GO termごとの登録頻度と情報量", f"{associated_gene_label}関連候補と対照候補のGO共有内訳"],
            ["候補側と疾患側で同一の出典に依存するGOを重複排除", "BP/MF/CC、希少・頻出term、Train収録・事後対応を区別して表示"],
            f"どのGO一致が{associated_gene_label}由来の既存情報の再提示であり、どこに他遺伝子由来の追加文脈があるかを記述できる。",
            "GO一致の数は独立実験件数でもKGE順位への寄与でもない。", go_refs[:29]
        ))

    if allele or papers:
        questions.append(_new_q(
            "ALLELE-PRIMARY", "当該配布系統・アレルに対応する実験原本を確認する",
            f"アレル記録={allele_id.get('mgi_allele_id', '未入力')}、候補固有一次実験論文={primary_paper_state or '未照合'}。",
            ["BRC配布系統とMGIアレル/遺伝背景の照合", "原著Methods・Resultsの遺伝型、系統、表現型測定", "必要なら当該系統の再測定計画"],
            ["原著・レビュー・web resourceを分ける", "別アレル/別背景の観測をこの配布系統へ自動転用しない"],
            "研究者がそのマウスを用途に適した候補と判断するための具体的な資料と追加測定を特定できる。",
            "一次論文が『未同定』であることは一次論文が存在しない証明ではない。", [str(allele_id.get('mgi_allele_id') or ''), str(pheno.get('phenotype_reference') or '')]
        ))

    questions.append(_new_q(
        "RETRIEVAL-CROSSCHECK", "SPARQL候補とKGE候補を同じ条件で比較する",
        ("同一条件のSPARQL候補登録を確認済み。" if known_sparql is True else
         "同一条件のSPARQL候補には含まれないことを確認済み。" if known_sparql is False else
         f"同一スナップショットのSPARQL候補包含は未照合。過去保存group一致={hist.get('status', '未確認')}は代用しない。"),
        ["同じ疾患IRI・取得日・KGスナップショット・候補集合定義のSPARQL結果", "凍結KGEファミリー別候補順位", "direct/indirect根拠の出典・時点"],
        ["SPARQLとKGEで共通・SPARQLのみ・KGEのみを集合として比較", "KGEのみでも既存Gene/MP/GOの学習情報や過去の別経路を点検"],
        "従来列挙法で見えにくい候補がどれか、同一条件のもとで評価できる。",
        "KGEのみの出現は、新規疾患モデルの確認ではない。また過去のmatched-Mouse group存在と比較時のSPARQL包含は同義ではない。", [disease_iri, mouse_iri]
    ))

    observations = {
        "candidate_mouse_gene_edges": len(mouse_gene),
        "candidate_mouse_mp_edges": len(mouse_mp),
        "candidate_mouse_go_train_edges": sum(x.get("evidence_type") == "FROZEN_TRAIN_MOUSE_GO" for x in intrinsic),
        "structural_paths_recorded": len(structural_paths),
        "candidate_mp_ids": sorted(mp_set),
        "disease_hp_mapped_mp_ids": sorted(mapped_mp),
        "candidate_mp_disease_mapped_mp_exact_intersection": mp_intersection,
        "go": go_stats,
        "historical_sparql_group": hist.get("status", "NOT_RECORDED"),
        "same_scope_sparql_candidate_verified": known_sparql,
        "allele_id": allele_id.get("mgi_allele_id") or None,
        "allele_symbol": allele_id.get("allele_symbol") or None,
        "phenotype_text": pheno.get("phenotype") or None,
        "phenotype_blood_glucose_11w_mg_dl": pheno.get("blood_glucose_11_weeks_mg_dl"),
        "candidate_specific_primary_paper_status": primary_paper_state or "NOT_RECORDED",
    }

    return {
        "extension_id": EXTENSION_ID,
        "purpose": "候補に対する研究者向け根拠・限界・次の検証提案。最終モデルを自動決定しない。",
        "candidate": {"disease_iri": disease_iri, "mouse_iri": mouse_iri,
                      "rbrc_id": candidate, "retrieval_source": identity.get("retrieval_source") or "未入力",
                      "family": family, "frozen_rank": rank,
                      "frozen_rank_sha256": ranking_sha or None,
                      "input_payload_sha256": payload_sha256},
        "observations": observations,
        "research_questions": questions,
        "evidence_index": evidence_index,
        "assessment_readonly": {
            "formal_f_class": assessment.get("f_class", "未記録"),
            "formal_hml": assessment.get("hml", "未記録"),
            "review_status": assessment.get("review_status", "未記録"),
            "provisional_ruleset": as_mapping(assessment.get("provisional_assessment")).get("ruleset_id"),
            "provisional_f_class": as_mapping(assessment.get("provisional_assessment")).get("proposed_f_class"),
            "provisional_hml": as_mapping(assessment.get("provisional_assessment")).get("proposed_hml"),
            "formal_state_mutated": False},
        "limitations": [
            "当該マウスが疾患モデルとして成立するかの最終判断は研究者が行う。",
            "KGE順位やSPARQL候補出現は疾患モデル妥当性の自動判定ではない。",
            "観察された構造的経路はKGE順位を形成した個々の原因の証明ではない。",
            "提案した検証は実施前であり、効果量・有意性・方向を予言しない。",
            "別手法・別時点のデータを同じ科学的検証結果として扱わない。",
            "正式F1–F4/HMLは既存専門家評価を維持し、暫定出力で変更しない。"
        ],
        "provenance_flags": {
            "primary_test_access": False, "test_access": False,
            "training": False, "validation_rescoring": False,
            "ranking_mutation": False, "network_retrieval": False,
            "llm_call": False},
        "researcher_decision": "本アプリは候補と検証すべき科学的問いを提示します。モデルとしての採否・実験用途への適合性は研究者が判断します。"
    }


def make_llm_followup_request(plan: Mapping[str, Any]) -> Dict[str, Any]:
    """Output data for an eventual 8510-only broker; never call an API."""
    return {
        "contract": "KGE_8504_LLM_FOLLOWUP_PROPOSAL_V0_7_UNCONNECTED",
        "role": "研究者のためにEvidenceと検証すべき問いを説明する。疾患モデルを採否判定しない。",
        "allowed_evidence_refs": sorted(as_mapping(plan.get("evidence_index")).keys()),
        "candidate": deepcopy(as_mapping(plan.get("candidate"))),
        "observations": deepcopy(as_mapping(plan.get("observations"))),
        "research_questions": deepcopy(as_list(plan.get("research_questions"))),
        "formal_evaluation": deepcopy(as_mapping(plan.get("assessment_readonly"))),
        "instructions": [
            "事実・推論・未検証・情報欠落を必ず区別する。",
            "各出典付きの事実にはallowed_evidence_refs内の識別子のみを付ける。",
            "実測のない効果量・KGE経路因果・PMID/DOI/IRI・疾患表現型を生成しない。",
            "研究者が判断するための追加実験・比較計算・データベース確認を提案する。",
            "疾患モデルとしての適否を結論・採点・推奨として自動決定しない。",
            "formal F1-F4/HMLと凍結順位を変更しない。",
            "このデータは8510への送信前の下書きであり、API呼出しを行った証明ではない。"
        ],
        "response_contract_example": {
            "source_facts": [{"text": "資料にある事実", "evidence_refs": []}],
            "interpretations": [{"text": "推論/未検証", "status": "hypothesis", "evidence_refs": []}],
            "next_checks": [{"question_id": "KGE-RANK-COMPARE", "rationale": "研究者向け検証理由", "evidence_refs": []}],
            "limitations": ["未検証事項"], "model_candidate_decision": None
        },
        "llm_call_performed": False,
    }


def validate_llm_followup_response(response: Any, plan: Mapping[str, Any]) -> Tuple[bool, List[str]]:
    """Structural/source-reference gate only; not scientific truth verification."""
    errors = []
    if not isinstance(response, dict):
        return False, ["応答がJSONオブジェクトではありません"]
    fields = {"source_facts", "interpretations", "next_checks", "limitations", "model_candidate_decision"}
    if set(response) != fields:
        errors.append("応答のキー集合が契約と一致しません")
    if response.get("model_candidate_decision", "MISSING") is not None:
        errors.append("モデル採否欄はnull以外にできません")
    valid_evidence = set(as_mapping(plan.get("evidence_index")))
    valid_questions = {x.get("question_id") for x in as_list(plan.get("research_questions")) if isinstance(x, dict)}
    specifications = {
        "source_facts": {"text", "evidence_refs"},
        "interpretations": {"text", "status", "evidence_refs"},
        "next_checks": {"question_id", "rationale", "evidence_refs"},
    }
    for group, keys in specifications.items():
        entries = response.get(group, [])
        if not isinstance(entries, list) or len(entries) > 50:
            errors.append(f"{group}の件数または型が不正です")
            continue
        for i, ent in enumerate(entries):
            if not isinstance(ent, dict) or set(ent) != keys:
                errors.append(f"{group}[{i}]のキーが不正です")
                continue
            refs = ent.get("evidence_refs")
            if not isinstance(refs, list) or len(refs) > 20 or any(not isinstance(x, str) or x not in valid_evidence for x in refs):
                errors.append(f"{group}[{i}]に未知の根拠IDがあります")
            textkey = "rationale" if group == "next_checks" else "text"
            if not isinstance(ent.get(textkey), str) or not ent[textkey].strip() or len(ent[textkey]) > 3000:
                errors.append(f"{group}[{i}]の本文が不正です")
            if group == "source_facts" and not refs:
                errors.append(f"{group}[{i}]に出典がありません")
            if group == "interpretations" and ent.get("status") not in ("hypothesis", "unverified", "interpretation"):
                errors.append(f"{group}[{i}]の仮説/未検証区分が不正です")
            if group == "next_checks" and ent.get("question_id") not in valid_questions:
                errors.append(f"{group}[{i}]の検証課題IDが不正です")
    limitations = response.get("limitations", [])
    if not isinstance(limitations, list) or len(limitations) > 50 or any(not isinstance(x, str) or len(x) > 3000 for x in limitations):
        errors.append("limitationsが不正です")
    return len(errors) == 0, errors


def _default_input_path() -> Path:
    env = os.environ.get("KGE_V07_EVIDENCE_JSON", "").strip()
    if env:
        return Path(env).expanduser()
    options = [
        Path.home() / "Downloads" / "KGE_V06_FIXED3_SHA_VERIFIED" / DEFAULT_FILENAME,
        Path.home() / "projects/kge/bridge_node2vec_2026/isolated/kge_evidence_v0_6" / DEFAULT_FILENAME,
    ]
    return next((p for p in options if p.is_file()), options[0])


def render_followup_panel_from_verified_input(*, expected_disease_iri: str | None = None, expected_mouse_iri: str | None = None, expected_family: str | None = None, expected_rank: int | None = None) -> None:
    """Append into an isolated copy of the existing 8504 V0.6 app."""
    import streamlit as st  # Existing 8504 environment only; no new venv.
    st.divider()
    st.header("次の科学的検証を考える — 候補解釈 V0.7.2（隔離）")
    st.info("本アプリは疾患に関連する実験マウスの候補と根拠・限界・追加検証を提示します。どの候補をモデルとして用いるかは研究者が判断します。")
    st.caption("既存のV0.6 Evidence解釈画面に追記する機能。正式8504/8502、凍結順位、F/HML、8510・API・鍵は変更しません。")
    file_path = st.text_input("読み取り専用Evidence JSON（候補を選んだ後に、その候補の固定入力を指定）", value=str(_default_input_path()), key="kge_v07_evidence_json_path")
    try:
        bundle, digest = read_json_readonly(Path(file_path))
        plan = make_next_steps(bundle, digest)
        candidate_for_gate = plan["candidate"]
        expected_identifiers = {
            "disease_iri": expected_disease_iri,
            "mouse_iri": expected_mouse_iri,
            "family": expected_family,
            "frozen_rank": expected_rank,
        }
        for key, expected_value in expected_identifiers.items():
            if expected_value is not None and candidate_for_gate.get(key) != expected_value:
                raise EvidenceContractError(
                    f"選択中の凍結候補とEvidence入力が不一致です: {key}。"
                    "別候補のEvidenceを転用しません。"
                )
    except (EvidenceContractError, OSError, ValueError) as exc:
        st.warning(f"Evidenceの固定入力を確認できません: {exc}")
        st.caption("V0.6でSHA確認済みのEVIDENCE_LLM_INPUT JSONを指定してください。候補の情報がない場合に研究者向け判定は作成しません。")
        return

    candidate = plan["candidate"]
    ob = plan["observations"]
    st.markdown(f"**対象疾患:** `{candidate['disease_iri']}`  ")
    st.markdown(f"**候補Mouse:** `{candidate['mouse_iri']}`  ")
    st.markdown(f"**探索手法:** `{candidate['family']}`／**凍結順位:** `{candidate['frozen_rank'] if candidate['frozen_rank'] is not None else '記録なし'}`")
    st.caption(f"読取JSON SHA256: {digest} ／ 出典独立性・KGE順位寄与の実験的検証とは別")

    a = plan["assessment_readonly"]
    st.markdown("#### 評価の状態（正式評価を変更しない）")
    st.write(f"正式F1–F4: **{a['formal_f_class']}** ／ 正式H/M/L: **{a['formal_hml']}** ／ レビュー: **{a['review_status']}**")
    if a["provisional_f_class"] or a["provisional_hml"]:
        st.caption(f"既存ルールによる暫定案: {a['provisional_f_class'] or '未記録'} / {a['provisional_hml'] or '未記録'}（専門家の正式判断ではない）")

    st.markdown("#### 原本から読み取れる候補情報")
    st.write(f"学習KGのMouse→Gene辺: {ob['candidate_mouse_gene_edges']}、Mouse→MP辺: {ob['candidate_mouse_mp_edges']}、Mouse→GO辺: {ob['candidate_mouse_go_train_edges']}")
    if ob["candidate_mp_ids"] or ob["disease_hp_mapped_mp_ids"]:
        st.write("候補側MP: " + ("、".join(ob["candidate_mp_ids"]) or "記録なし"))
        st.write("疾患側HP→MP: " + ("、".join(ob["disease_hp_mapped_mp_ids"]) or "記録なし"))
        st.caption("表示された集合の完全一致がなくても、疾患との関係がないことの証明にはなりません。")
    if ob["allele_id"]:
        st.write(f"当該候補のアレルID: {ob['allele_id']}／アレル表記: {ob['allele_symbol'] or '未記録'}")
    if ob["phenotype_text"]:
        text = f"候補側の表現型注釈: {ob['phenotype_text']}"
        if ob["phenotype_blood_glucose_11w_mg_dl"] is not None:
            text += f"／11週齢の血糖値として記録: {ob['phenotype_blood_glucose_11w_mg_dl']} mg/dL"
        st.write(text)
        st.caption("この記録は当該アレルの注釈内容です。疾患の全病態や配布個体での再現性をアプリが判定するものではありません。")
    go = ob["go"]
    if go["completeness"] == "GO_CONTEXT_PRESENT":
        label = go['candidate_linked_gene_label']
        st.write(f"GO共有: {go['shared_exact_go_count']}件（{label}のみ {go['candidate_gene_only_shared_go']}、同Geneと他遺伝子 {go['candidate_gene_and_other_shared_go']}、別Geneのみ {go['other_gene_only_shared_go']}、未分類 {go['unclassified_shared_go']}）。")
        st.caption("GO件数＝独立証拠数ではありません。また共有GOのうち凍結Trainに直接Mouse–GO辺がないものは事後的文脈です。")
    if ob["same_scope_sparql_candidate_verified"] is None:
        st.caption("過去のSPARQL＋LLM matched-Mouse group収録と、同じ条件のSPARQL候補であることは区別します。")

    st.markdown("#### 研究者が次に確かめられる科学的問い")
    for q in plan["research_questions"]:
        with st.expander(f"{q['question_id']}｜{q['title']}｜{q['status']}", expanded=False):
            st.write("**今回確認できた情報:** " + q["observed_basis"])
            st.write("**必要なデータ:** " + "／".join(q["required_data"]))
            st.write("**検証の方法:** " + "／".join(q["verification_method"]))
            st.write("**分かり得ること:** " + q["possible_interpretation"])
            st.write("**まだ分からないこと:** " + q["interpretation_limit"])
            st.caption("原本で照合可能な識別子: " + (", ".join(q["evidence_refs"][:20]) or "対応なし"))

    st.markdown("#### 根拠・検証課題の引き渡し（API呼び出しなし）")
    st.download_button("研究者向け検証課題をJSON保存", data=json.dumps(plan, ensure_ascii=False, indent=2),
                       file_name="KGE_8504_RESEARCH_NEXT_STEPS_V0_7.json", mime="application/json", key="kge_v07_plan_json_download")
    llm_request = make_llm_followup_request(plan)
    st.download_button("LLM解釈用の根拠固定入力案をJSON保存（8510未接続）", data=json.dumps(llm_request, ensure_ascii=False, indent=2),
                       file_name="KGE_8504_LLM_FOLLOWUP_REQUEST_UNCONNECTED_V0_7.json", mime="application/json", key="kge_v07_llm_request_download")
    st.caption("上記は実LLM応答ではありません。8510既存BYOK・brokerへの接続は行っていません。V0.6の固定3ファイルも変更しません。")

    with st.expander("外部で生成されたLLM解釈JSONの検査（任意・API呼び出しなし）", expanded=False):
        uploaded = st.file_uploader("出典ID付きJSON（V0.7追加契約）", type=["json"], key="kge_v07_llm_response_upload")
        if uploaded is not None:
            try:
                if uploaded.size > 500 * 1024:
                    raise EvidenceContractError("応答JSONが500KBを超えています")
                response = json.loads(uploaded.getvalue())
                okay, problems = validate_llm_followup_response(response, plan)
                if okay:
                    st.success("出典IDと形式の検査PASS。本文の科学的真偽および研究者による評価は未確認です。")
                    for ent in response["source_facts"]:
                        st.write("**出典付き観測:** " + ent["text"])
                        st.caption(", ".join(ent["evidence_refs"]))
                    for ent in response["interpretations"]:
                        st.write(f"**{ent['status']}（LLM解釈）:** " + ent["text"])
                        st.caption(", ".join(ent["evidence_refs"]))
                    for ent in response["next_checks"]:
                        st.write(f"**{ent['question_id']}（追加検証案）:** " + ent["rationale"])
                else:
                    st.error("LLM出力を表示しません。" + "／".join(problems[:8]))
            except (json.JSONDecodeError, EvidenceContractError, UnicodeDecodeError) as exc:
                st.error(f"LLM応答JSONの検査に失敗しました: {exc}")

    st.markdown("**最終判断について:** " + plan["researcher_decision"])

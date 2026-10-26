#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated 8504 V0.7.1: sortable 6-family Top-N comparison, missing ranks last.

Only the six-family comparison table is intercepted. The original DataFrame,
rank values, candidate identities, frozen data, and other st.dataframe calls
remain unchanged. Rendered HTML stays entirely inside a local Streamlit iframe.
"""
from __future__ import annotations

import html
import json
import math
from typing import Any

RANK_COLUMNS = (
    'node2vec_rank', 'TransE_rank', 'RotatE_rank',
    'ComplEx_rank', 'CompGCN_rank', 'RDF2Vec_rank',
)
MOUSE_COLUMNS = ('mouse_iri', 'mouse_id')


def _as_frame(data: Any) -> Any:
    """Unwrap a pandas Styler if the native application passes one."""
    if not hasattr(data, 'columns') and hasattr(data, 'data') and hasattr(data.data, 'columns'):
        return data.data
    return data


def is_target_comparison(data: Any) -> bool:
    """Allow only the precise 6-family combined table, not every DataFrame."""
    data = _as_frame(data)
    try:
        cols = set(data.columns)
        return bool(set(RANK_COLUMNS).issubset(cols) and set(MOUSE_COLUMNS).issubset(cols))
    except (TypeError, AttributeError):
        return False


def is_missing(v: Any) -> bool:
    """Missing means unset, not rank zero. No mutation of underlying values."""
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip().lower() in {'', 'none', 'null', 'nan', 'nat', '<na>'}
    if isinstance(v, float):
        return math.isnan(v)
    # Pandas NA/NaT (locally supported runtime library, already used by 8504).
    try:
        import pandas as pd
        result = pd.isna(v)
        return bool(result)
    except (TypeError, ValueError, ImportError):
        return False


def _scalar(v: Any) -> Any:
    if is_missing(v):
        return None
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, str):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return float(v) if math.isfinite(v) else None
    # numpy scalar/pandas nullable integer, but NEVER impute missing rank.
    if hasattr(v, 'item'):
        try:
            return _scalar(v.item())
        except (ValueError, TypeError, AttributeError):
            pass
    return str(v)


def prepare_table(data: Any) -> dict:
    if not is_target_comparison(data):
        raise ValueError('Only the 6-family Top-N comparison table is supported')
    data = _as_frame(data)
    columns = list(data.columns)
    if len(columns) != len(set(columns)):
        raise ValueError('Duplicate column names would misrepresent the frozen comparison')
    if len(data) > 2000:
        raise ValueError('Unexpectedly large Top-N table; refusing partial display')
    records = []
    # Position iteration avoids pandas to_dict() NaN representation ambiguity.
    for values in data.itertuples(index=False, name=None):
        records.append([_scalar(v) for v in values])
    return {'columns': columns, 'rows': records,
            'numeric_columns': [c for c in columns if c in RANK_COLUMNS or c == 'methods_in_topN']}


def compare_values(a: Any, b: Any, descending: bool = False, numeric: bool = False) -> int:
    """Python oracle for the exact JS comparator contract. None is last ALWAYS."""
    ma, mb = is_missing(a), is_missing(b)
    if ma != mb:
        return 1 if ma else -1
    if ma and mb:
        return 0
    if numeric:
        aa, bb = float(a), float(b)
        sign = (aa > bb) - (aa < bb)
    else:
        aa, bb = str(a), str(b)
        sign = (aa > bb) - (aa < bb)
    return -sign if descending else sign


_JS = r'''(function(){
  "use strict";
  const payload = JSON.parse(document.getElementById("payload").textContent);
  const columns = payload.columns;
  const rows = payload.rows.map((values, index) => ({values, index}));
  const numeric = new Set(payload.numeric_columns);
  const table = document.getElementById("grid");
  const thead = document.getElementById("header");
  const tbody = document.getElementById("body");
  const announce = document.getElementById("announcement");
  let sortColumn = columns.indexOf("node2vec_rank");
  let direction = "asc";

  function missing(value) {
    return value === null || value === undefined ||
      (typeof value === "number" && !Number.isFinite(value)) ||
      (typeof value === "string" && ["", "none", "null", "nan", "nat", "<na>"].includes(value.trim().toLowerCase()));
  }
  function compareCells(a, b, col, dir) {
    const am = missing(a), bm = missing(b);
    if (am !== bm) return am ? 1 : -1; // null ALWAYS at bottom in BOTH directions
    if (am) return 0;
    let cmp;
    if (numeric.has(columns[col])) {
      const av = Number(a), bv = Number(b);
      cmp = av < bv ? -1 : av > bv ? 1 : 0;
    } else {
      cmp = String(a).localeCompare(String(b), "ja", {numeric: true, sensitivity:"base"});
    }
    return dir === "desc" ? -cmp : cmp;
  }
  function renderBody() {
    const ordered = rows.slice();
    if (sortColumn >= 0) {
      ordered.sort((a,b) => compareCells(a.values[sortColumn], b.values[sortColumn], sortColumn, direction) || a.index-b.index);
    }
    const fragment = document.createDocumentFragment();
    for (const row of ordered) {
      const tr = document.createElement("tr");
      for (const val of row.values) {
        const td = document.createElement("td");
        td.textContent = missing(val) ? "None" : String(val);
        if (missing(val)) td.classList.add("missing");
        tr.appendChild(td);
      }
      fragment.appendChild(tr);
    }
    tbody.replaceChildren(fragment);
    for (const th of thead.querySelectorAll("th")) {
      const i = Number(th.dataset.column);
      th.setAttribute("aria-sort", i !== sortColumn ? "none" : direction === "asc" ? "ascending" : "descending");
      th.querySelector(".indicator").textContent = i !== sortColumn ? "" : direction === "asc" ? " ▲" : " ▼";
    }
    announce.textContent = (sortColumn < 0 ? "元の表示順" : columns[sortColumn] + "：" + (direction === "asc" ? "昇順" : "降順")) + "。Noneは常に末尾。";
  }
  for (let i=0; i<columns.length; i++) {
    const th = document.createElement("th");
    th.dataset.column = i;
    const btn = document.createElement("button");
    btn.type="button";
    btn.textContent = columns[i];
    const indicator = document.createElement("span");
    indicator.className="indicator";
    btn.appendChild(indicator);
    btn.addEventListener("click", () => {
      if (sortColumn === i) direction = direction === "asc" ? "desc" : "asc";
      else {sortColumn = i; direction = "asc";}
      renderBody();
    });
    th.appendChild(btn);
    thead.appendChild(th);
  }
  renderBody();
})();'''


def make_safe_html(data: Any) -> str:
    payload = prepare_table(data)
    json_text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    # Critical when data from a query may contain </script> or HTML markup.
    json_text = json_text.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return '''<!doctype html><html lang="ja"><head><meta charset="utf-8" />
<style>
:root{color-scheme:dark;}body{margin:0;color:#fafafa;background:#0e1117;font:13px sans-serif}
.notice{margin:0 0 8px;color:#a8b4c5} .scroll{overflow:auto;max-height:580px;border:1px solid #3d414d;border-radius:5px}
table{border-collapse:collapse;white-space:nowrap;min-width:100%;font-variant-numeric:tabular-nums}
th,td{border-right:1px solid #343842;border-bottom:1px solid #343842;padding:8px 10px;text-align:left}
th{position:sticky;top:0;background:#1b1d27;z-index:1;font-weight:500}
th button{border:0;color:#dce2eb;background:transparent;padding:0;cursor:pointer;font:inherit;text-align:left}
th button:focus-visible{outline:2px solid #76b6fb;outline-offset:4px}
tr:hover td{background:#1b1d27}td.missing{color:#7f8795;font-style:italic}
.indicator{color:#ed5b5b}#announcement{margin:7px 0;color:#9dbbd5;font-size:12px}
</style></head><body>
<p class="notice">列見出しを押すと昇順・降順を切り替えます。<strong>None（Top-N圏外）は常に末尾</strong>です。凍結順位は変更しません。</p>
<div class="scroll"><table id="grid" aria-label="6手法Top-N凍結順位比較"><thead><tr id="header"></tr></thead><tbody id="body"></tbody></table></div>
<p id="announcement" role="status" aria-live="polite"></p>
<script id="payload" type="application/json">''' + json_text + '''</script>
<script>''' + _JS + '''</script></body></html>'''


def install_rank_comparison_renderer() -> None:
    """Wrap Streamlit dataframe only for the confirmed comparison-column signature."""
    import streamlit as st
    if getattr(st.dataframe, '_kge_v071_wrapped', False):
        return
    original = st.dataframe

    def dataframe_with_nulls_last(data=None, *args, **kwargs):
        if not is_target_comparison(data):
            return original(data, *args, **kwargs)
        # If unsupported content is encountered, fail closed rather than
        # silently reverting to the original incorrect interactive sorting.
        html_text = make_safe_html(data)
        import streamlit.components.v1 as components
        components.html(html_text, height=670, scrolling=False)
        return None

    dataframe_with_nulls_last._kge_v071_wrapped = True
    st.dataframe = dataframe_with_nulls_last

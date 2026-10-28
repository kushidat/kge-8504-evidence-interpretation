# 8504 Evidence Interpretation -> SPARQL+LLM handoff

## Scope
Read-only integration design only. Do not modify 8501/8510 accepted behavior without separate approval.

## Current finding
8510 v1.0 owns BYOK/Fernet key storage inside its Streamlit application. The accepted implementation decrypts the user key only for LLM execution and passes `OPENAI_API_KEY` to child processes. No externally callable broker/API for another app was identified in the reviewed implementation.

## Requested design
Provide a minimal, isolated LLM broker boundary that remains owned by the SPARQL+LLM workstream and can accept:
- fixed Evidence Bundle JSON
- fixed prompt template
- fixed JSON output schema
- requested model setting

and return strict JSON output without exposing the API key to 8504.

## Required invariants
- 8504 must never read or store the OpenAI API key.
- Existing 8510 encrypted key store remains the secret authority.
- No PRIMARY_TEST / TEST / withheld access.
- No SPARQL re-query, network evidence retrieval, ranking mutation, training, validation rescoring, or model selection.
- Input/output hashes and model name must be logged; secret values must not be logged.
- LLM output remains `PROVISIONAL_LLM_NOT_EXPERT_REVIEWED` and cannot mutate formal F1-F4/HML/review status.
- Identifiers absent from input Evidence Bundle must cause fail-closed validation.
- The existing 8510 accepted workflows must remain unchanged unless explicitly approved.

## Current 8504 candidate responsibility
The KGE workstream prepares and validates the Evidence Bundle, prompt, and expected output schema only. API/BYOK execution is not implemented in V0.6.

## FIX8追加の重要な信用境界（2026-10-26、隔離案）

- F06の`ranking_verification.receipt_sha256`は内容の整合性用であり、電子署名や公式ローダー実行の証明ではない。
- FIX8のStreamlit wrapperは、SHA固定の公式8504ローダーが返した順位行を確認し、JSONに書き出さない同一プロセス内の検証コンテキストを発行する。Evidence Bundle全体とこのコンテキストを結び付けた場合にのみF04応答検査を許可する。
- JSONファイルやbroker API経由で受け取ったEvidence Bundleはコンテキストを再構成できない。受信先は自分の信頼境界で公式ローダーを再実行・再照合し、新しいEvidence Bundleを生成する必要がある。**受信済み`receipt_sha256`だけを受け入れない。** 8510側API設計・デプロイは未実施・未承認。
- 外部からPythonコードを実行できる攻撃者、検証済みhelperを差し替えられる攻撃者、または全デプロイ環境を不正に変更できる攻撃者に対しての真正性を、この一時コンテキストで保証するものではない。
- 過去SPARQL＋LLMの7原本はSHA確認した同じ読み込みバイト列からJSON解析する。初回の証明とキャッシュの有効期間はローカルファイルのinode/size/mtime/ctimeに依存する。メタデータ偽造まで想定する環境は別途不変スナップショットが必要。
- 既存FIX7・GitHub Draft PR #2・正式8504 v1.0・8502 v1.0・凍結原本・primary_testは変更していない。

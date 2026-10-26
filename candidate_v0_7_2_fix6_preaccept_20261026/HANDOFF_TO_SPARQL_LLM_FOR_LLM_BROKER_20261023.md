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

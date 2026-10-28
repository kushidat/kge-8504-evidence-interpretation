#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$ROOT/app/streamlit_app_8504_v1_0_2_emergency_scope_correction.py"
BASE="$HOME/projects/kge/bridge_node2vec_2026/streamlit_app__FX9B_GFINAL_AUDIT_CANDIDATE_V0_1_FIX1_20261009.py"
EXPECTED_BASE='4de02002017698a3453b0567ddd44ea629945888fba3e57f05043e48aabd47ca'
PORT="${1:-8504}"
case "$PORT" in 8504|18570) ;; *) echo 'HOLD_PORT_MUST_BE_8504_OR_18570';exit 1;; esac
PY="$HOME/projects/mondo_eval/venv_hybrid/bin/python"
[ -x "$PY" ] || { echo HOLD_VENV_PYTHON_UNAVAILABLE; exit 1; }
[ -f "$APP" ] || { echo HOLD_APP_NOT_FOUND; exit 1; }
(cd "$ROOT" && shasum -a 256 -c SHA256SUMS.txt >/dev/null) || { echo HOLD_DISTRIBUTION_SHA; exit 1; }
printf '%s  %s\n' "$EXPECTED_BASE" "$BASE" | shasum -a 256 -c - >/dev/null || { echo HOLD_BASE_SHA; exit 1; }
OWNERS=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true)
[ -z "$OWNERS" ] || { echo "HOLD_PORT_${PORT}_OCCUPIED_BY=$OWNERS";exit 1; }
mkdir -p "$ROOT/operations"
PIDFILE="$ROOT/operations/$PORT.pid"
LOGFILE="$ROOT/operations/$PORT.log"
[ ! -e "$PIDFILE" ] && [ ! -e "$LOGFILE" ] || { echo HOLD_RELEASE_OPERATIONS_ALREADY_EXIST;exit 1; }
PYTHONDONTWRITEBYTECODE=1 nohup "$PY" -B -m streamlit run "$APP" \
 --server.address=127.0.0.1 --server.port="$PORT" \
 --server.headless=true --server.fileWatcherType=none \
 --browser.gatherUsageStats=false > "$LOGFILE" 2>&1 < /dev/null &
PID=$!
printf '%s\n' "$PID" > "$PIDFILE"
I=0
PASS=0
while [ "$I" -lt 20 ]; do
 OWNERS=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true)
 HTTP=$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/_stcore/health" 2>/dev/null || true)
 if [ "$OWNERS" = "$PID" ] && [ "$HTTP" = '200' ];then PASS=1;break;fi
 if ! kill -0 "$PID" 2>/dev/null;then break;fi
 I=$((I+1));sleep 1
done
if [ "$PASS" -ne 1 ];then
 echo "HOLD_HEALTH_OR_PID;PORT=$PORT;PID=$PID;OWNERS=$OWNERS;HTTP=$HTTP"
 echo "CHECK_LOG=$LOGFILE"
 exit 1
fi
echo '8504_V1_0_2_RC2_MAC_LOCAL_PROCESS=PASS'
echo "PORT=$PORT"
echo "PID=$PID"
echo 'HTTP=200'
echo "URL=http://127.0.0.1:$PORT"
echo 'SCIENCE_REVIEW=NOT_ACCEPTED'
echo 'SPARQL_LLM_GENERIC_COMPARISON=NOT_CONNECTED'
echo 'OFFICIAL_V1_0_SOURCE=UNCHANGED'

#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$ROOT/app/streamlit_app_8504_v1_0_2_emergency_scope_correction.py"
BASE="$HOME/projects/kge/bridge_node2vec_2026/streamlit_app__FX9B_GFINAL_AUDIT_CANDIDATE_V0_1_FIX1_20261009.py"
EXPECTED_BASE='4de02002017698a3453b0567ddd44ea629945888fba3e57f05043e48aabd47ca'
PORT="${1:-8504}"
case "$PORT" in 8504|18570) ;; *) echo 'HOLD_PORT_MUST_BE_8504_OR_18570';exit 1;; esac
PIDFILE="$ROOT/operations/$PORT.pid"
[ -f "$PIDFILE" ] || { echo NOT_RUNNING_NO_PIDFILE;exit 0; }
PID=$(cat "$PIDFILE")
case "$PID" in *[!0-9]*|'') echo HOLD_PIDFILE_VALUE;exit 1;; esac
CMD=$(ps -ww -p "$PID" -o command= 2>/dev/null || true)
case "$CMD" in *streamlit*streamlit_app_8504_v1_0_2_emergency_scope_correction.py*) ;; *) echo HOLD_PROCESS_IDENTITY;exit 1;; esac
OWNERS=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true)
[ "$OWNERS" = "$PID" ] || { echo "HOLD_PORT_OWNER=$OWNERS";exit 1; }
kill "$PID"
I=0
while [ "$I" -lt 15 ] && kill -0 "$PID" 2>/dev/null;do I=$((I+1));sleep 1;done
OWNERS=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | sort -u || true)
[ -z "$OWNERS" ] || { echo "HOLD_PORT_${PORT}_STILL_OCCUPIED=$OWNERS";exit 1; }
STAMP=$(date +%Y%m%d_%H%M%S)
RECEIPT="$ROOT/operations/$PORT.stopped.$STAMP.pid"
[ ! -e "$RECEIPT" ] || { echo HOLD_STOP_RECEIPT_COLLISION;exit 1; }
mv "$PIDFILE" "$RECEIPT"
echo '8504_V1_0_2_RC2_PROCESS_STOPPED=PASS'
echo "PORT=$PORT"
echo 'LOG_IS_PRESERVED=YES'

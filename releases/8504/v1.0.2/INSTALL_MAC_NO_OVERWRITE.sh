#!/bin/sh
set -eu
ZIP="${1:?usage: INSTALL_MAC_NO_OVERWRITE.sh /Users/.../Downloads/KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028.zip}"
PREFIX='KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028'
PARENT="$HOME/projects/kge/bridge_node2vec_2026/releases"
DEST="$PARENT/$PREFIX"
BASE="$HOME/projects/kge/bridge_node2vec_2026/streamlit_app__FX9B_GFINAL_AUDIT_CANDIDATE_V0_1_FIX1_20261009.py"
EXPECTED_BASE='4de02002017698a3453b0567ddd44ea629945888fba3e57f05043e48aabd47ca'
[ -f "$ZIP" ] || { echo HOLD_ZIP_NOT_FOUND;exit 1; }
[ -f "$BASE" ] || { echo HOLD_OFFICIAL_BASE_MISSING;exit 1; }
printf '%s  %s\n' "$EXPECTED_BASE" "$BASE" | shasum -a 256 -c - >/dev/null || { echo HOLD_BASE_SHA;exit 1; }
[ ! -e "$DEST" ] || { echo "HOLD_RELEASE_DEST_ALREADY_EXISTS=$DEST";exit 1; }
unzip -tq "$ZIP" >/dev/null || { echo HOLD_ZIP_CRC;exit 1; }
mkdir -p "$PARENT"
unzip -q "$ZIP" "$PREFIX/*" -d "$PARENT"
(cd "$DEST" && shasum -a 256 -c SHA256SUMS.txt) || { echo HOLD_DISTRIBUTION_SHA;exit 1; }
echo "V102_RC2_PLACED=$DEST"
echo 'OFFICIAL_APP_GIT_OLD_RELEASE_MODIFIED=NO'
echo "NEXT_PREVIEW=/bin/sh '$DEST/RUN_LOCAL_RELEASE_8504.sh' 18570"

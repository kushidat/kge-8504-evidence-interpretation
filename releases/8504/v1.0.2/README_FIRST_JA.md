# 8504 v1.0.2 緊急是正（Mac限定）— 最初に読む

**2026-10-28 / 範囲誤認インシデント対応。v1.0.1の技術的受入履歴は保全し、科学的な汎用Evidence機能の受入は事後再審査中です。**

## 今回の実装上の事実
- 6手法KGE順位と固定Frozen Train/GOの読み取り部分を継承（選択した疾患・マウスに合わせた処理）。正式FX9B FIX1の原本とSHAは変更しません。
- 1疾患に固定された過去SPARQL+LLMの7JSONの自動照合を除去しました。同疾患・候補の現行SPARQL+LLM結果は**未接続**です。検索結果がない、とは判断していません。
- 1候補に固定された外部系統・アレル・原著snapshotと、その固定症例だけのF3/Medium提案を新リリースから外しました。候補固有外部根拠は**未接続・未評価**です。
- 固定症例だけの研究課題自動提示を新リリースのUIから外しました。汎用的な科学的課題生成は**未実装**です。
- 画面に版番号、日本語説明、上位50件CSV専用ダウンロード、6状態表示の展開欄を追加しています。
- 実LLM・8510連携、学習・順位変更、TEST/PRIMARY_TEST/WITHHELDの閲覧は行いません。

## 新規テストと残る受入
- 新規変更部分のpytest合成試験9/9 PASS（T2D、ALS、melanomaの3つの疾病IDを用いたモック。実原本の新たな科学的解析ではありません）。
- 研究者向けWordマニュアル4ページを作成しレンダリング表示確認済み。
- Macでのv1.0.2実起動と実データ画面、CSVダウンロード、GitHub v1.0.2 Releaseは**未実施**（Macログ・GitHub公開後に判定）。
- REG04 11項目の正式閉鎖0/11、PR3 Draft/未マージ、研究室・別ホスト配備未許可、PRIMARY_TEST embargoは継続。

## 無上書きMac受領・安全なプレビュー
1. Google Drive経由でこのZIPをMacの `~/Downloads/` に保存。会話内で示すSHA256と `unzip -tq` を確認。
2. 以下を実行（既存v1.0.1を停止しない）。

```
ZIP="$HOME/Downloads/KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028.zip"
unzip -tq "$ZIP"
unzip -p "$ZIP" 'KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028/INSTALL_MAC_NO_OVERWRITE.sh' | /bin/sh -s -- "$ZIP"
ROOT="$HOME/projects/kge/bridge_node2vec_2026/releases/KGE_8504_V1_0_2_RC2_MAC_LOCAL_20261028"
/bin/sh "$ROOT/RUN_LOCAL_RELEASE_8504.sh" 18570
/bin/sh "$ROOT/CHECK_LOCAL_RELEASE_8504.sh" 18570
open 'http://127.0.0.1:18570'
```

3. 画面で **非T2D疾患** を選択し、SPARQL+LLMが「未接続」、外部原著・アレルが「未評価」、凍結順位とGOが表示されることを確認してください。T2Dも選び、旧7JSON／旧暫定F3/Mediumが再表示されないことを確認。TOP50は50行、`KGE_8504_<MONDO>_<手法>_TOP50_YYYYMMDD_HHMMSS_JST.csv`。
4. 18570番の検証がPASSした後、旧v1.0.1をユーザー自身が明示的に停止してから、`RUN_LOCAL_RELEASE_8504.sh 8504` を実行します。今回の新スクリプトは旧プロセスを止めません。8504占有時はHOLDします。
5. previewの停止：`/bin/sh "$ROOT/STOP_LOCAL_RELEASE_8504.sh" 18570`。再起動前は操作ログを保全（既存ログ上書きを防ぐため自動再起動しません）。

## 開発・GitHub
- この配布ZIPは**GitHub上の新タグやRelease公開を自動的に意味しません**。リポジトリは現状Private、アクセス権がこちらにないためGitHub操作は別途Macの認証済みgit/ghから実施・確認します。
- 旧v1.0.1のGitHubタグ、PR #3、main、旧版配布フォルダーは変更しません。
- 新ソースの差分は `qa/CHANGED_SOURCE_UNIFIED_DIFF.patch`、改訂履歴は `RELEASE_MANIFEST.json` に記載。


## RC2 additional changes and limits
- Timestamped Top50 CSV names use Asia/Tokyo JST at button render; not necessarily time of click. CSV rows and ranks are unchanged.
- Removed stale F3/Medium caption in the LLM tab; provisional F/HML remains Not assessed.
- Prior v1.0.2 preview 18569 received user PASS for T2D, ALS, melanoma, GO and CSV; new RC2 18570 is not yet verified on Mac.
- GitHub Release v1.0.2 is not yet published; 8504 production port is not switched.

# 8504 Evidence Interpretation v1.0.4 | 最小操作マニュアル

## 適用範囲
2026-11-07 V14承認済み開発順序1～6のみ。8504固定KGE順位・Evidence・正式F/HML/G4は更新しません。LLMの生物学的説明は暫定であり、科学的妥当性や順位因果の証明ではありません。
本配布候補は研究室Macの既存固定8504・8510 V10・KGEデータを使う**環境依存版**です。単独のZIPを任意のPCで起動できると主張しません。

## 必要条件
既存 `~/projects/kge/bridge_node2vec_2026`、固定版8504、ローカルPython仮想環境 `~/projects/mondo_eval/venv_hybrid`、V14で受入済みのStage3/4C/Stage12/8510 V10のコードとデータ。既存正式アプリ/8502/8510は変更しません。既設ポート18530～18534を停止しません。

## 起動・確認・終了（Mac）
以下のディレクトリを利用：
`~/projects/mondo_eval/release_records/8504_8510/isolated/8504_V104_RELEASE_CANDIDATE_20261107_V01`

`python3 "$HOME/projects/mondo_eval/release_records/8504_8510/isolated/8504_V104_RELEASE_CANDIDATE_20261107_V01/MANAGE_V104.py" verify`

`python3 "$HOME/projects/mondo_eval/release_records/8504_8510/isolated/8504_V104_RELEASE_CANDIDATE_20261107_V01/MANAGE_V104.py" start`

ブラウザ `http://127.0.0.1:18535/`。確認後に停止：

`python3 "$HOME/projects/mondo_eval/release_records/8504_8510/isolated/8504_V104_RELEASE_CANDIDATE_20261107_V01/MANAGE_V104.py" stop`

再開は `start`。状態確認は `status`。停止操作はこの版が生成したPIDのみを対象とし、正式8504・8510や他ポートは停止しません。

## 操作
8504で疾患/候補マウス（手法と順位）を選び、固定Evidenceを確認します。必要に応じて既存8510 JSON/Markdownを手動受領できます。8510 APIを使用する場合は、BYOKを入力して `Save BYOK for this session` を押し、`BYOK Status: saved` を確認した後、送信同意をチェックし `Run LLM interpretation once` を一度押します。送信内容に候補IDとEvidenceが含まれ、課金の可能性があります。自動送信・自動再送はありません。APIキーはセッションメモリのみで、再起動すると再入力が必要です。キーをチャットや出力ファイルに貼り付けないでください。

回答画面の Markdown/JSON ダウンロード、または `Save these provisional Markdown/JSON files without overwrite` を使用します。ファイル名には MONDO、KGE手法、順位、RBRC-ID、gpt-6-luna、JST日時、入力/出力ハッシュ短縮値を記載します。既済の過去結果はAPIを再送せず従来どおり保管します。

## 異常時の対応
画面が表示されない場合は `status` を実行し、同じ18535を起動し直す前に占有PIDを確認してください。`start` は既存ポートを強制停止しません。`BYOK not saved` は保存操作後に確認します。`STAGE4E...` はフェーズを記録し、自動再送せず結果を保全します。固有の新規クリック実行履歴は残します。旧attemptマーカーは削除しません。

## 科学的限界・公開保護
8510回答は暫定解釈です。出典照合のHOLD、未実証事項、GO重複、KGE順位の因果説明未実証を保持します。PRIMARY_TEST、validation/test/withheld、KGEの原本、APIキーをGitHub公開物に含めません。REG04/REG06/REG07の旧判定を自動解除しません。

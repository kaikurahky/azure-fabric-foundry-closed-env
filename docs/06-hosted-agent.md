# 6. Hosted Agent: コンテナから直接データ取得

[目次](../README.md) | [前](./05-prompt-agent.md) | [次](./07-azure-files.md)

Hosted Agents は Preview を含む機能です。作成時点の提供状況、利用制約を [Hosted Agents](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)で確認します。サンプルは **Responses 2.0** と Microsoft Agent Framework の hosting API を使います。

## 6-1. 実行場所と identity

| 方式 | データ取得コードの場所 | 使う業務データ経路 |
|---|---|---|
| BYO Hosted | Foundry の Hosted コンテナ | `subnet-foundry-agent` → `pep-data-blob`／`pep-data-postgres` |
| Managed Hosted | Microsoft Managed VNet の Hosted コンテナ | `pep-managed-blob`／`pep-managed-postgres` |

現行仕様では、プラットフォームが Hosted Agent ごとに **Microsoft Entra Agent identity** を作成します。Project MI、Foundry account MI、Agent identity は別です。

- **Project MI**: ACR image pull 等。
- **Account MI**: Managed network の PE 承認等。
- **Agent identity**: 実行中コードのモデル／外部データアクセス。

`DefaultAzureCredential()` がコンテナ内で利用するプラットフォーム identity に、必要なデータ権限を付与します。自分の VM のログインをコンテナへコピーしません。

根拠: [Hosted permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions)。

## 6-2. プローブ入りコンテナをビルドする

主なファイル:

- [hosted_main.py](../samples/hosted_main.py): Agent に `read_private_marker` 関数ツールを登録。
- [network_probe.py](../samples/network_probe.py): DNS を確認してから実データを取得。Public／loopback／link-local の IP を成功にしない。
- [Dockerfile.hosted](../samples/Dockerfile.hosted): Linux コンテナ。

VM / ビルド VM の `samples` ディレクトリ:

```bash
az acr login --name "acrffnw<suffix>"
docker build -f Dockerfile.hosted -t "acrffnw<suffix>.azurecr.io/hosted-probe:v1" .
docker push "acrffnw<suffix>.azurecr.io/hosted-probe:v1"
```

パッケージの API が更新された場合、[公式 Responses host](https://learn.microsoft.com/agent-framework/hosting/foundry-hosted-agent)と [Hosted deploy](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent)を確認。`requirements-hosted.txt` は作成時にローカル import／定義生成を確認したバージョンで固定しています。Azure 実機での互換性は別途検証し、成功した image digest と全依存バージョンを記録してください。hosting package は Preview 版です。

Responses host の既定 port は **8088**（プラットフォームが `PORT` を渡した場合はそれに従う）です。独自 HTTP サーバーに置き換える場合も Foundry hosting protocol／port と合わせます。

## 6-3. Project identity に ACR pull 権限

各 Foundry Project の Identity → System assigned principal ID を確認し、共通 ACR に pull 権限を付ける。

1. ACR の role assignment mode を確認。
2. 従来 RBAC なら `AcrPull`、ABAC repository mode なら `Container Registry Repository Reader` 等を付与。
3. BYO は customer VNet の `pep-acr` の DNS と到達性。
4. Managed は `pep-managed-acr` の Approved 状態を確認。

ACR への経路が正常でも権限がなければ image pull は失敗します。

## 6-4. BYO Hosted をデプロイ

VM 上に Python venv を作り、デプロイ SDK を入れます（Agent Framework はこの管理用 venv には不要）。

```bash
python -m venv .venv
source .venv/bin/activate
pip install "azure-ai-projects==2.7.0" "azure-identity==1.26.0"
```

PowerShell の場合は `.venv\Scripts\Activate.ps1`。以下の `export` は Bash です。[.env.example](../samples/.env.example)は入力値一覧で、スクリプトは `.env` を自動読込しません。自分で環境変数を設定します。

```bash
export FOUNDRY_PROJECT_ENDPOINT="<BYO Project endpoint>"
export FOUNDRY_MODEL_NAME="<実際の model deployment name>"
export HOSTED_AGENT_NAME="hosted-nwtest-byo"
export HOSTED_IMAGE="acrffnw<suffix>.azurecr.io/hosted-probe:v1"
export STORAGE_ACCOUNT="stffnw<suffix>"
export PGHOST="pg-ffnw-<suffix>.postgres.database.azure.com"
export PGUSER="hosted_byo_reader"
export EXPECTED_MARKER="lab-20261008-001"
python deploy_hosted.py
```

管理用の `az login` はこの VM 内で行います。Project endpoint へ HTTPS で到達できる必要があります。

成功すると name／version、状態 `active` が表示されます。15 分で active にならない場合は停止し、Agent logs／provisioning error を調べます。**active はコンテナ起動の成功で、データ取得成功ではありません。**

## 6-5. 作成された Agent identity にデータ権限

1. Foundry の Agent 詳細／Identity 情報から Agent principal ID を確認。見つからない場合は [Agent identity 公式説明](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-identity)と Project の Agent identity 情報を確認。
2. ID が Project MI／Account MI でないことを確認。
3. データ Storage に **Storage Blob Data Reader** を付ける。
4. PostgreSQL の Entra admin で [DB 章](./02-data-sources.md)の `hosted_byo_reader` をその Principal ID へ関連付け、SELECT を付与。
5. 権限反映を待つ。

作成前には Agent identity が存在しないため、**デプロイ → identity 確認 → 権限付与 → データ試験**の順序です。

## 6-6. BYO の呼び出しとログ

```bash
export HOSTED_AGENT_VERSION="<deploy が返した version>"
python invoke_hosted.py
```

SDK 呼び出しも閉域 VM から行います。応答だけでなく、Foundry の Hosted Agent logs／trace に以下の証跡があることを確認:

- `Hosted data probe` の timestamp と `execution_label=hosted-nwtest-byo`。
- Blob の `resolved_ips` が PE Private IP。
- PostgreSQL の `resolved_ips` が PE Private IP。
- Blob／DB の `marker` が一致。

DB の `inet_client_addr()`／`inet_server_addr()` は補助情報です。PaaS の proxy／NAT により Agent の Subnet IP と一致しない場合があるため、それだけで経路を判定しません。

**呼び出し元の VM ではなく Hosted ログでデータ取得が実行された**ことが重要です。モデルが tool を呼ばなければ未合格。ツール出力なしのもっともらしい文章を証跡にしません。

## 6-7. Managed Hosted をデプロイして比較する

前章の Managed outbound rules:

- `pep-managed-self`（model / project access）
- `pep-managed-acr`（image pull）
- `pep-managed-blob`
- `pep-managed-postgres`

が利用可能であることを確認します。

```bash
export FOUNDRY_PROJECT_ENDPOINT="<Managed Project endpoint>"
export FOUNDRY_MODEL_NAME="<Managed側の model deployment name>"
export HOSTED_AGENT_NAME="hosted-nwtest-managed"
export PGUSER="hosted_managed_reader"
python deploy_hosted.py
```

1. 作成された **Managed 側 Agent identity** を取得。
2. Blob Data Reader、DB の `hosted_managed_reader` マッピングと SELECT を付与。
3. `HOSTED_AGENT_VERSION` を Managed の version に更新。
4. `python invoke_hosted.py`。
5. Managed 側 Hosted ログ／trace の実行 label、Private IP、marker を確認。

Managed の `resolved_ips` は、自分の `pep-data-blob` の `10.42.1.x` と一致する必要はありません。Managed 側 MPE の Private IP であり customer-visible NIC がありません。**target ID、subresource、Approved rule、公開遮断、実データ取得をセット**で判定します。

## 6-8. 更新と負テスト

- 新しい試験で marker を変更する場合は Blob／DB と Agent 環境変数を一致させ、同じ agent name の **新しい version**を作る。version を指定して呼ぶ。
- 一時的に Agent の Blob Reader を外すと、データアクセスが権限エラーとなる。権限を戻したあと再試験する。共有テストの同時実行中には行わない。
- VNet 外から同じ Project／Agent を呼び、公開アクセスの拒否を確認する。
- Public への FQDN rule や Storage trusted-services bypass を追加して失敗を隠さない。
- 最新 marker はプロンプトに書かず、**データソースから取得した値**と確認する。

Image 更新には新しい tag／digest を使います。`latest` の上書きだけでは再現性がありません。正式版への説明では成功した image digest／package versions／Agent version を残します。

# 5. Prompt Agent: private MCP 経由でデータを読む

[目次](../README.md) | [前](./04-foundry-network.md) | [次](./06-hosted-agent.md)

## 5-1. 今回のツール実行場所

```text
BYO Prompt → subnet-foundry-agent → pep-tools-environment
Managed Prompt → Managed VNet → pep-managed-tools
                                   ↓
                         ca-nwtest-mcp（subnet-tools）
                                   ↓
                     pep-data-blob / pep-data-postgres
```

**Prompt Agent が PostgreSQL の TCP 接続を直接張っているのではありません。**Prompt は private MCP を呼び、MCP コンテナがデータソースを読みます。

これは「Prompt のツール呼び出しが閉域」「ツールのデータ取得が閉域」という二段階の試験です。最終結果の Blob／DB IP は MCP 内の DNS 観測です。Foundry から MCP への前半は PE／MPE の設定・承認状態・実行 trace・公開遮断で確認します。

## 5-2. ACR を作成する（Hosted と共用）

1. Azure Portal → Container registries → Create。
2. 同 RG／Region、名前 `acrffnw<suffix>`、**Premium**（Private Link 対応）。
3. Admin user = Disabled。
4. Networking → Public network access = Disabled。
5. PE `pep-acr` を `subnet-pe` に作成、subresource `registry`、DNS zone `privatelink.azurecr.io`。
6. Registry endpoint と data endpoint の DNS レコードがあることを確認。Managed Foundry に [前章](./04-foundry-network.md)の `pep-managed-acr` を作成。

ビルド／push をするユーザーには registry の権限モードに合わせた Writer を付与します。従来 Registry RBAC は `AcrPush`、ABAC の Registry + Repository Permissions は **Container Registry Repository Writer** 等が必要です。pull は従来なら `AcrPull`、ABAC なら **Container Registry Repository Reader**。モードが違うロールを付けても成功しません。

根拠: [ACR role modes](https://learn.microsoft.com/azure/container-registry/container-registry-rbac-built-in-roles-overview)、[Hosted deployment permissions](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent)。

## 5-3. ツールの Managed Identity

1. Portal → Managed Identities → Create → `id-mcp-reader`、同 RG／Region。
2. Client ID と Principal ID を控える。
3. Storage Blob Data Reader をデータ Storage に付与。
4. [DB 章](./02-data-sources.md)で `mcp_reader` をこの Principal ID に関連付け、SELECT を付与。
5. 後で Container App にこの **User Assigned MI** を割り当てる。

MI の Client ID はコードの選択用、Principal ID は RBAC／DB 登録用です。

## 5-4. MCP コンテナをビルドする

VM 内の Docker が動く Bash で、このリポジトリの `samples` に移動します。Windows VM で Docker が使えない場合は、同 VNet の Linux ビルド VM を使います。**閉域 ACR へ Public ビルドサービスが自動で到達できるとは考えない**でください。

```bash
az acr login --name "acrffnw<suffix>"
docker build -f Dockerfile.mcp -t "acrffnw<suffix>.azurecr.io/mcp-probe:v1" .
docker push "acrffnw<suffix>.azurecr.io/mcp-probe:v1"
```

Docker の外部 base image／Python packages 取得は管理用 outbound が必要です。インストール時に失敗したら通信許可と依存バージョンを確認します。Private データアクセスの成功とは別の工程です。

## 5-5. Container Apps 環境と PE

1. Portal → Container Apps → Create、名前 `ca-nwtest-mcp`、同 RG／Region。
2. Create new environment → `cae-nwtest-tools`、**workload profiles** 環境。
3. Networking → Use your own virtual network = Yes。
4. VNet `vnet-fabric-foundry-lab`、専用 `subnet-tools`。VNet injection はデータソース PE に到達するために必要です。
5. Environment の Public Network Access = **Disabled**。
6. Enable private endpoint = Yes → **`pep-tools-environment`**、VNet／`subnet-pe`、DNS integration = Yes。target は **environment**、group ID は **`managedEnvironments`**。
7. Container image = `acrffnw<suffix>.azurecr.io/mcp-probe:v1`。
8. Container App に `id-mcp-reader` を割り当て、registry pull にもその ID を選択。ID に ACR の Reader／AcrPull を付与。
9. Ingress = Enabled、HTTP、target port **8000**、**Accepting traffic from outside the Container Apps environment** を選ぶ。

「outside environment」でも environment の公開アクセスを Disabled にすれば、ここで作った PE から到達させる構成です。Ingress を app 内部だけにすると、外から private MCP として呼べない場合があります。

10. Revision は検証では single revision、min replicas = 1 にして cold start を避ける。
11. 起動用環境変数／secret を設定する。

| 設定 | 値 |
|---|---|
| `DATA_IDENTITY_CLIENT_ID` | `id-mcp-reader` の Client ID |
| `STORAGE_ACCOUNT` | `stffnw<suffix>` |
| `PGHOST` | 通常の PostgreSQL FQDN |
| `PGUSER` | `mcp_reader` |
| `EXPECTED_MARKER` | 最新の試験 marker |
| `EXECUTION_LABEL` | `private-mcp-container` |
| `PGSSLROOTCERT` | `/etc/ssl/certs/ca-certificates.crt` |
| `MCP_LAB_TOKEN` | Container App secret の参照 |
| `MCP_HOSTNAME` | 実際の MCP app FQDN（scheme／path なし） |

MCP token は `python -c "import secrets; print(secrets.token_urlsafe(32))"` 等で自分の環境で生成し、**Container App の secret と Foundry の project connection だけに保存**します。コード／GitHub／ログに記録しません。このラボの独自 middleware は不正 token を 401 と明示し、読み取り先を固定しています。本番用の Entra token 検証／認可実装の代わりではありません。

12. Create／Deploy。Revision が Healthy になるまで待つ。
13. アプリの実際の FQDN を控える。MCP URL は **`https://<app-fqdn>/mcp`**。

初回作成時に FQDN がまだ不明なら `MCP_HOSTNAME=localhost` で起動し、作成後に実際の FQDN へ更新して新 revision を稼働させます。localhost のままで外部から MCP 接続試験をしないでください。サンプルは DNS rebinding 保護を有効なまま、指定 FQDN だけを許可します。

根拠: [Container Apps Private Endpoint](https://learn.microsoft.com/azure/container-apps/how-to-use-private-endpoint)。

## 5-6. ツール入口を先に確認する

VM で MCP FQDN の DNS を解決し、`pep-tools-environment` の Private IP であることを確認。

```powershell
Resolve-DnsName <MCP app FQDN>
Test-NetConnection <MCP app FQDN> -Port 443
```

- token なしの `/mcp` 呼び出し → **401**（これは内部到達＋認証拒否の証跡）。
- 有効 token の MCP client で `tools/list` と `read_private_marker` → 実データ成功。
- `read_private_marker_with_files` は追加 Files 章を完了するまで呼ばない。
- 外部 PC からの到達は environment の公開遮断で失敗。

例として VS Code の `.vscode/mcp.json` を**検証用 VM のローカル設定だけ**に作れます。ヘッダー値は入力変数を使い、ファイルに直接 token を書かないでください。

```json
{
  "inputs": [
    {"type":"promptString","id":"mcp-token","description":"Lab MCP token","password":true}
  ],
  "servers": {
    "private-lab": {
      "type":"http",
      "url":"https://<app-fqdn>/mcp",
      "headers":{"x-lab-tool-token":"${input:mcp-token}"}
    }
  }
}
```

最初に VM からツールを試すのは MCP／DB の不具合を切り分けるためです。この成功だけでは Prompt Agent の送信試験に合格していません。

## 5-7. BYO Prompt Agent を作成する

1. VM 内の新 Foundry portal → **BYO Project**。
2. Build → Agents → Create agent → **Prompt**。
3. 名前 `prompt-nwtest-byo`、前章で作成したモデル deployment を選択。
4. Instructions:

```text
検証用エージェントです。データ検証の要求では read_private_marker を必ず呼んでください。
ツールの JSON、resolved_ips、marker を省略せず返してください。
ツールを呼べない場合は失敗と報告し、推測や過去の会話で補わないでください。
```

5. Tools → Add → Custom → Model Context Protocol (MCP)。
6. URL = `https://<app-fqdn>/mcp`。
7. Authentication = **Key-based**。ヘッダー名 **`x-lab-tool-token`**、値 = Container App secret と同じ token。
8. connection を `conn-private-mcp` として Project に保存する。SDK を使う場合はこの connection を `project_connection_id` に指定し、コードに token を渡さない。
9. Allowed tools は `read_private_marker` のみに限定。Approval = **Always**。
10. Save、Playground から「今すぐ read_private_marker で取得し、JSON を返してください」と要求。
11. 表示された tool approval を確認し Approve。最新 marker を確認。
12. Agent run の Tool trace と、Container Apps → Log stream の `Completed private data probe` を突き合わせる。

**Bing / Websearch / SharePoint 等の Public endpoint ツールは追加しない**でください。VNet 分離されていても、それらのツールは Public endpoint を使います。

## 5-8. Managed Prompt Agent で同じ試験

1. [前章](./04-foundry-network.md)の `pep-managed-tools` outbound rule を MCP **environment** ID に向けて作成／承認。
2. Foundry Managed Project → Prompt `prompt-nwtest-managed` を作る。
3. 同じ MCP URL／token を、この Project の別 connection に保存する。Project 間で connection は自動共有されません。
4. 同じ instructions、tool allow-list、Approval Always。
5. 新しい marker に Blob／DB／MCP の `EXPECTED_MARKER` を更新。
6. Playground の実行、tool trace、MCP ログの時刻と marker を記録。

Managed Prompt が Blob を読むための `pep-managed-blob` があっても、この MCP 経由の **後半**はそれを使いません。データアクセス元はツール側 `subnet-tools` で、`pep-data-blob`／`pep-data-postgres` を使います。

## 5-9. 合否

- 両 Foundry account の公開入口が Disabled、VM 内の認証付き Agent 呼び出しが成功。
- Foundry → MCP が BYO PE／Managed MPE で成立し、MCP の公開入口は Disabled。
- MCP → Blob／DB の結果に Private IP と最新 marker がそろう。
- 有効な認証を使っても外部 PC の公開経由データアクセスは拒否。
- token なし／間違いの MCP 呼び出しは 401。401 をネットワーク障害と混同しない。

根拠: [Foundry private tool traffic](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link#agent-tools-with-network-isolation)、[MCP tools / project connection](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol)、[Managed tools 公式サンプル](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/18-managed-virtual-network)。

# 1. 準備と共通ネットワーク

[目次](../README.md) | [前](./00-architecture.md) | [次](./02-data-sources.md)

## 1-1. 作成前チェック

| 必要なもの | 確認する場所／理由 |
|---|---|
| Azure Subscription | Portal → Subscriptions。課金と Policy の適用先 |
| Contributor + RBAC を割り当てる権限 | Owner、または Contributor + Role Based Access Administrator 等。Contributor 単独では RBAC 不可 |
| Fabric administrator | Tenant Private Link 設定に必要。Azure Owner と別の権限 |
| Fabric 有料 F capacity | 入口 Private Link は **Trial capacity 非対応**。ラボは F2 等の小さい有料 SKU から検討 |
| Fabric workspace admin | Workspace の MPE／接続／Lakehouse を作る |
| Foundry roles | 作成者に Foundry Account Owner、Agent 作成に Foundry User／Project Manager 等。名称変更中は旧 Azure AI 名が表示される場合あり |
| Model quota | Foundry → Models / Quotas。ネットワークが正しくてもモデル枠ゼロなら動かない |
| Policy 承認 | PE、Private DNS、VM、Bastion、Container Apps、ACR、User Assigned MI、キー禁止の適用範囲 |

**既存のお客様環境／業務テナントでは Tenant Public Access を勝手に遮断しない**でください。Fabric の設定は RG 内に限定されません。専用テナントを推奨します。

### リージョン

ラボの第一候補は `Japan East / japaneast`。作成時に以下を再確認し、対応しない機能／モデルがあれば共通して使えるリージョンを選びます。

- Fabric tenant home region と capacity region が Data Engineering 対応。
- VNet data gateway の対応リージョン。
- Foundry の BYO / Managed と Hosted Agent、使うモデル、SKU の対応。
- Foundry BYO のアカウントと VNet は同リージョン。

Managed VNet の Learn の現行対応一覧には Japan East が含まれています。ただしモデル提供・クォータまで保証するものではありません。[公式 Managed VNet](https://learn.microsoft.com/azure/foundry/how-to/managed-virtual-network)を作成日に再確認します。

### 費用

最低でも Fabric capacity、VM／ディスク、Bastion、PE、PostgreSQL、ACR Premium、Container Apps の環境 PE、Hosted の計算時間、モデル token が課金対象です。Managed の FQDN outbound rule を追加すると Azure Firewall 費用も発生し得ます。

1. Portal → Cost Management → Budgets → 検証用予算と通知を作る。
2. 各作成画面の SKU／見積もりを確認する。F2 が一律最安／常に十分と断定しない。
3. Managed の本ガイドでは、まず PE rule のみを使い、任意 FQDN rule は追加しない。
4. VM を停止しても PE、Bastion、ディスク等は残る。[片付け](./09-troubleshooting-cleanup.md)まで計画する。

## 1-2. 命名と IP 計画

`<suffix>` は自分専用の英数字小文字。Storage／ACR の名前は世界で一意、ハイフン不可です。

| リソース | 名前／範囲 |
|---|---|
| RG | `rg-fabric-foundry-nwtest` |
| VNet | `vnet-fabric-foundry-lab` : `10.42.0.0/16` |
| VM subnet | `subnet-client` : `10.42.0.0/24` |
| PE subnet | `subnet-pe` : `10.42.1.0/24` |
| Fabric gateway | `subnet-fabric-gateway` : `10.42.2.0/24`、`Microsoft.PowerPlatform/vnetaccesslinks` 委任 |
| Foundry BYO runtime | `subnet-foundry-agent` : `10.42.3.0/24`、`Microsoft.App/environments` 委任 |
| MCP Container Apps | `subnet-tools` : `10.42.4.0/24`、workload profiles 環境用 |
| Bastion | `AzureBastionSubnet` : `10.42.5.0/26`、予約名の例外 |
| VM / Bastion | `vm-lab-client` / `bas-nwtest` |
| Blob / Files account | `stffnw<suffix>`、Standard StorageV2、LRS |
| PostgreSQL | `pg-ffnw-<suffix>` |
| Foundry account | `foundry-ffnw-byo-<suffix>` / `foundry-ffnw-managed-<suffix>` |
| Projects | `proj-nwtest-byo` / `proj-nwtest-managed` |
| ACR | `acrffnw<suffix>`、Premium |
| Tool identity / environment / app | `id-mcp-reader` / `cae-nwtest-tools` / `ca-nwtest-mcp` |

この CIDR が既存 VPN／Peering と重複しないか確認します。Foundry とツールで delegated subnet を共有してはいけません。

## 1-3. Portal で RG と VNet を作る

1. `https://portal.azure.com` → Resource groups → Create。
2. Subscription を選択、RG に **`rg-fabric-foundry-nwtest`**、Region に Japan East → Review + create → Create。
3. Virtual networks → Create → 同 RG、名前 `vnet-fabric-foundry-lab`、同 Region。
4. IP addresses → 既定アドレスを上表の `10.42.0.0/16` に変更。
5. 上表の Subnet を作成。専用サービスの Delegation は表どおりに設定。`subnet-pe` にはサービスを委任しない。
6. `subnet-client` のインターネットへの送信は後述の NAT Gateway で明示的に構成する。既定 outbound access に依存しない。
7. Review + create → Create。VNet の DNS servers はラボでは **Default (Azure-provided)** のまま。

Container Apps の subnet delegation は作成ウィザード／[公式 custom VNet](https://learn.microsoft.com/azure/container-apps/custom-virtual-networks)に従い `Microsoft.App/environments` を指定します。

## 1-4. VM と Bastion

Windows VM にブラウザーを置き、そのブラウザーから Fabric／Foundry を操作します。自分の PC で Portal を開くのと、VM 内のブラウザーで開くのは違います。

1. Virtual machines → Create → 名前 `vm-lab-client`、同 RG／Region、Windows Server のサポート対象イメージ。
2. サイズはブラウザー／SDK／Docker が動くものを選ぶ。Docker のビルドが重ければ後で Linux ビルド VM を同 `subnet-client` に追加する。
3. 管理者パスワードを設定。Networking → 上記 VNet／`subnet-client`、**Public IP = None**、公開 inbound ports = None。
4. Identity → System assigned = On（VM から Managed Identity を試す場合）。
5. NAT gateways → `nat-lab-client` を同 RG に作成し、Public IP を割り当て、`subnet-client` に関連付ける。これはサインイン／更新／パッケージ取得用の送信です。データソース PE の通信は NAT に出しません。
6. Bastions → Create → `bas-nwtest`、同 VNet、`AzureBastionSubnet`、専用 Public IP、Standard 等の利用する SKU。
7. VM → Connect → Bastion → VM の管理者資格情報で接続。
8. VM 内の Edge で Azure Portal と Fabric にサインインできることを確認。

Bastion のブラウザー接続サービスと NAT の Public IP は管理用です。「Private IP でデータアクセス」する設計でも管理通信は別途必要です。全 Internet 遮断を求める本番では、許可済み proxy／Firewall／VPN に置き換えます。

## 1-5. ツールと Resource Provider

管理操作は自分の PC／Cloud Shell でもできますが、**閉域データアクセス／SDK の Agent 呼び出しは VM 内**で実行します。通常の Cloud Shell はこの VNet 内にいません。

VM に Azure CLI、Python 3.11 以上、Git、必要に応じて Docker を導入。Bash コマンドは Linux VM または Windows VM の WSL / Git Bash 等で実行します。PowerShell の DNS 試験はそのまま利用できます。

`python --version` を確認します。Linux で `python` がない場合は `python3 --version` を確認し、このガイドの `python` を `python3` に読み替えてください。venv を有効にした後は通常 `python` が使えます。

```bash
az login
az account set --subscription "<検証 Subscription ID>"
az account show --query '{subscription:id,tenant:tenantId}' -o json
az version
```

Managed VNet の CLI は公式記事で **2.86.0 以上**が必要とされ、command group は Preview です。古ければ CLI を更新してから進めます。下の Provider は必要なものを Register（Portal → Subscription → Resource providers）。

```text
Microsoft.Network
Microsoft.Compute
Microsoft.Storage
Microsoft.DBforPostgreSQL
Microsoft.CognitiveServices
Microsoft.PowerBI
Microsoft.PowerPlatform
Microsoft.App
Microsoft.ContainerRegistry
Microsoft.OperationalInsights
Microsoft.ManagedIdentity
Microsoft.KeyVault
Microsoft.Search
Microsoft.ContainerService
```

Standard サンプルを使う場合は、その README の追加 Provider／RBAC／Quota も満たします。

## 1-6. DNS の原則

PE の作成時に **Integrate with private DNS zone = Yes** を選び、同 RG の zone をこの VNet にリンクします。自分で同名 zone を何個も作らないでください。

| 宛先 | Private DNS zone |
|---|---|
| Blob | `privatelink.blob.core.windows.net` |
| Files | `privatelink.file.core.windows.net` |
| PostgreSQL PE | `privatelink.postgres.database.azure.com` |
| Foundry | `privatelink.services.ai.azure.com`、`privatelink.openai.azure.com`、`privatelink.cognitiveservices.azure.com` |
| Fabric Tenant | `privatelink.analysis.windows.net`、`privatelink.pbidedicated.windows.net`、`privatelink.prod.powerquery.microsoft.com` |
| ACR | `privatelink.azurecr.io` |
| Container Apps | `privatelink.<region>.azurecontainerapps.io` |

Container Apps の app FQDN に必要な environment 固有レコード／wildcard は PE ウィザードと [公式 DNS 手順](https://learn.microsoft.com/azure/container-apps/how-to-use-private-endpoint)に従います。Managed MPE の DNS は Foundry／Fabric 側が扱います。この customer VNet の zone をリンクしただけでは Managed 側の経路は作れません。

**到達目標:** VM へ Public IP なしで接続でき、必要な管理用 Web ページが開ける。まだデータソースの閉域試験は行っていません。

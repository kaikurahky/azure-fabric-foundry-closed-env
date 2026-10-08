# 4. Foundry の入口・BYO VNet・Managed VNet

[目次](../README.md) | [前](./03-fabric.md) | [次](./05-prompt-agent.md)

**新 Foundry portal / Responses API の Agent Service**を対象にします。classic hub の Azure Machine Learning managed network の記事／Assistants API の記事を混ぜません。

## 4-1. 比較用に 2 アカウントを作る理由

方式は作成時の重要な設定で、後から自由に切り替える機能ではありません。以下を別々に作り、同じ Blob／PostgreSQL を読みます。

| 方式 | Account | Project | Agent runtime |
|---|---|---|---|
| BYO | `foundry-ffnw-byo-<suffix>` | `proj-nwtest-byo` | `subnet-foundry-agent` |
| Managed | `foundry-ffnw-managed-<suffix>` | `proj-nwtest-managed` | Microsoft Managed VNet |

## 4-2. BYO: Portal から新規作成

1. `subnet-foundry-agent` は /24、**`Microsoft.App/environments`**委任、他サービス未使用であることを確認。
2. Azure Portal → Foundry → Create。RG／Region は共通、Account name は BYO 用。
3. Storage / Agent service の構成は **Basic / platform-managed**を選ぶ。自分の Search／Cosmos／Storage を選ばない。
4. Network → Public access = **Disabled**。
5. Add Private Endpoint → 名前 `pep-foundry-byo`、VNet／`subnet-pe`、target **account**、Private DNS integration = Yes。
6. **Virtual network injection** → 同 VNet、`subnet-foundry-agent` を選ぶ。
7. Review + create。Injection が設定されたことを必ず確認してから Create。
8. 作成後、新 Foundry portal `https://ai.azure.com` に **VM 内のブラウザーから**アクセス。
9. Project `proj-nwtest-byo` を作成／選択。Project endpoint を控える。

Portal に injection の選択肢が表示されない場合は、単なる PE だけのアカウントを作らず、[公式 BYO 手順](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link#create-a-new-resource-and-project-with-virtual-network-injection)と [Basic VNet テンプレート](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet)を確認します。テンプレートは自動生成名を含むので、実行前に VNet／Subnet／PE 名を本規約に合わせ、既存 VNet の重複作成を避ける必要があります。

> 公式資料には、network configuration が最初の Hosted Agent 作成時に有効になる旨の注意があります。本ラボは [Hosted 章](./06-hosted-agent.md)の最初の revision を作ってから Prompt 試験を行う順でも構いません。Prompt の結果から injection を推測せず、アカウント設定と実通信で判断してください。

## 4-3. Managed: REST と CLI から新規作成

現行の公式手順では **Managed network 作成は Portal UI 非対応**です。入口 PE の UI と混同しないでください。

以下は VM の Bash で実行する管理用コマンドです。`<...>` を置換します。課金開始前に RG／Subscription を確認してください。

```bash
RG="rg-fabric-foundry-nwtest"
SUB="<Subscription ID>"
ACCOUNT="foundry-ffnw-managed-<suffix>"
LOCATION="japaneast"
API="2026-05-01"
ACCOUNT_ID="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$ACCOUNT"

az rest --method PUT \
  --url "https://management.azure.com${ACCOUNT_ID}?api-version=$API" \
  --headers "Content-Type=application/json" \
  --body "{
    \"location\":\"$LOCATION\",
    \"kind\":\"AIServices\",
    \"sku\":{\"name\":\"S0\"},
    \"identity\":{\"type\":\"SystemAssigned\"},
    \"properties\":{
      \"allowProjectManagement\":true,
      \"customSubDomainName\":\"$ACCOUNT\",
      \"publicNetworkAccess\":\"Disabled\",
      \"disableLocalAuth\":true,
      \"networkInjections\":[{
        \"scenario\":\"agent\",
        \"subnetArmId\":\"\",
        \"useMicrosoftManagedNetwork\":true
      }]
    }
  }"
```

`disableLocalAuth=true` は本ラボが Foundry に Entra 認証だけで接続するための選択です。公式の作成例と異なる点です。

作成状態を確認:

```bash
az cognitiveservices account show -g "$RG" -n "$ACCOUNT" \
  --query '{state:properties.provisioningState,identity:identity.principalId}' -o json
```

`Succeeded` になるまで先に進まない。失敗は Deployment／Activity Log で確認します。

Foundry account の MI に、まず **account 自身**を scope にして接続承認権限を付けます。業務データ／MCP 環境は後で対象ごとに同ロールを付与。

```bash
PRINCIPAL=$(az cognitiveservices account show -g "$RG" -n "$ACCOUNT" \
  --query identity.principalId -o tsv)
az role assignment create \
  --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "b556d68e-0be0-4f35-a333-ad7ee1ce17ea" --scope "$ACCOUNT_ID"

az cognitiveservices account managed-network create \
  -g "$RG" -n "$ACCOUNT" \
  --managed-network allow_only_approved_outbound --firewall-sku Standard
```

`Azure AI Enterprise Network Connection Approver` は **ネットワーク接続を承認するロール**です。Blob 読み取り／DB SELECT 権限ではありません。

Portal → この Managed account → Networking → Private endpoint connections → Add:

- 名前 **`pep-foundry-managed`**
- target subresource **account**
- customer VNet の `subnet-pe`
- Private DNS integration = Yes、Foundry の 3 zone を同 VNet へリンク

ここは **VM から入る入口**です。Managed network 内の outbound PE とは別です。

VM 内の新 Foundry portal で Project `proj-nwtest-managed` を作ります。Project 作成が UI に表示されない場合は、新 Foundry であること／RBAC を確認し、[公式 Foundry project 作成ガイド](https://learn.microsoft.com/azure/foundry/how-to/create-projects)を参照。classic hub を代わりに作らないでください。

## 4-4. Managed の送信 PE rule を作る

Managed 側には、少なくとも self Foundry、Blob、PostgreSQL、MCP environment、ACR を許可する **Private Endpoint outbound rule** を用意します。

まず各 ARM ID を Portal → Properties / JSON view で控えます。

| 自分が付ける rule 名 | ARM target | Subresource target |
|---|---|---|
| `pep-managed-self` | Managed Foundry account | `account` |
| `pep-managed-blob` | データ用 Storage account | `blob` |
| `pep-managed-postgres` | PostgreSQL Flexible Server | `postgresqlServer` |
| `pep-managed-tools` | Container Apps **environment** | `managedEnvironments` |
| `pep-managed-acr` | ACR Premium | `registry` |
| `pep-managed-file`（追加章） | データ用 Storage account | `file` |

作成者が、target ごとに Managed account の MI に Network Connection Approver ロールを付与します。

```bash
TARGET_ID="<対象 ARM ID>"
az role assignment create \
  --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "b556d68e-0be0-4f35-a333-ad7ee1ce17ea" --scope "$TARGET_ID"
```

次を表の rule ごとに実行:

```bash
az cognitiveservices account managed-network outbound-rule set \
  -g "$RG" -n "$ACCOUNT" \
  --rule "pep-managed-blob" --type privateendpoint \
  --destination "<Storage account ARM ID>" --subresource-target blob
```

CA 環境／ACR は [公式 Managed サンプル 18](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/18-managed-virtual-network)の hosted-tools 構成も照合します。各サービスの group ID は、必要なら以下で確認:

```bash
az network private-link-resource list --id "$TARGET_ID" \
  --query '[].{group:groupId,requiredMembers:requiredMembers}' -o json
```

CLI／target が非対応というエラーが出たら Public rule で代用せず、API version、リージョン、公式サンプルとの差を調べます。

確認:

```bash
az cognitiveservices account managed-network show -g "$RG" -n "$ACCOUNT"
az cognitiveservices account managed-network outbound-rule list -g "$RG" -n "$ACCOUNT"
```

- isolation mode が **AllowOnlyApprovedOutbound**。
- target の PE 接続が Approved、rule が利用可能状態。`Pending` を成功扱いしない。
- Managed PE には customer-visible NIC がない。自分の `subnet-pe` に見つからなくても異常ではない。

## 4-5. 両方式の入口を確認する

両 account について VM から:

```powershell
Resolve-DnsName <account>.services.ai.azure.com
Test-NetConnection <account>.services.ai.azure.com -Port 443
```

通常の Project endpoint は以下の形式ですが、**Portal の実際の値を使います**。

```text
https://<account>.services.ai.azure.com/api/projects/<project>
```

1. account の `publicNetworkAccess=Disabled` と PE Approved を確認。
2. 新 Foundry portal の Project／モデル操作が VM 内で成功。
3. VNet 外で同じ認証を持つユーザーがデータプレーンを呼ぶと拒否される。
4. 後続章の Agent SDK 呼び出しでも入口を確認する。

## 4-6. モデルを用意する

各 Project → Build → Models / Deployments → chat-capable model を Deploy。作成時に利用可能なモデル／SKU／Quotaを選び、**モデル名ではなく Deployment name** を控えます。特定モデルが Japan East にあるとは決めつけません。

Global / Data Zone の deployment の処理地域は VNet のリージョンだけからは決まりません。データ所在地の要件がある場合はモデル deployment の種類を別途確認します。

必要権限:

- 検証ユーザー: Project の Foundry User／Project Manager、実行のみなら Foundry Agent Consumer 等。
- Project identity: account の model access など、作成時に設定された権限を確認。
- Hosted Agent identity: 外部データには別途 RBAC／DB role を付ける。

Public PE を付けただけで outbound は Private になった、と結論しないでください。次の 2 章で Agent 実行場所からの実アクセスを検証します。

# 公式資料と確認した判断

[目次](../README.md)

**確認日: 2026-10-08。** Microsoft Learn の検索と本文取得、Microsoft 公開サンプルの README を用いて確認しました。直接接続型 Learn MCP が利用できなかったため、Azure MCP の documentation 経由および公式 Web ページ取得を利用しました。以下はサービス仕様／手順の根拠で、Azure 上での動作成功の証跡ではありません。

## Fabric

| ID | Microsoft Learn | 確認した内容／ガイド |
|---|---|---|
| F1 | [Tenant Private Link overview](https://learn.microsoft.com/fabric/security/security-private-links-overview) | 対応 workload、Trial 非対応、capacity DNS 反映、on-prem gateway 制限／3・9章 |
| F2 | [Tenant Private Link setup](https://learn.microsoft.com/fabric/security/security-private-links-use) | Tenant settings、PowerBI ARM リソース、Tenant PE、3 DNS zones、公開遮断／3章 |
| F3 | [Managed PE overview](https://learn.microsoft.com/fabric/security/security-managed-private-endpoints-overview) | Notebook/Spark 等の対応範囲、managed network、地域条件／0・3章 |
| F4 | [Managed PE create / sources](https://learn.microsoft.com/fabric/security/security-managed-private-endpoints-create) | 作成／承認、Azure File Storage／PostgreSQL の target resource 対応／3・7章 |
| F5 | [Azure Blob connector overview](https://learn.microsoft.com/fabric/data-factory/connector-azure-blob-storage-overview) | VNet gateway、Organizational account／Service principal、Pipeline の Workspace identity／0・3章 |
| F6 | [Azure Blob connection](https://learn.microsoft.com/fabric/data-factory/connector-azure-blob-storage) | 接続作成の UI／3章 |
| F7 | [PostgreSQL database connector](https://learn.microsoft.com/fabric/data-factory/connector-postgresql-overview) | Dataflow Gen2 対応、VNet gateway、Basic／3章 |
| F8 | [Azure Database for PostgreSQL connector](https://learn.microsoft.com/fabric/data-factory/connector-azure-database-for-postgresql-overview) | Pipeline／Copy job、gateway、Basic。F7 と混同しない／3章 |
| F9 | [Azure Files connector](https://learn.microsoft.com/fabric/data-factory/connector-azure-files-overview) | 現行 Fabric は Account key のみ。ADF の MI 対応を転用しない／7章 |
| F10 | [VNet data gateway creation](https://learn.microsoft.com/data-integration/vnet/create-data-gateways) | Provider／subnet delegation／capacity／対応地域／1・3章 |
| F11 | [NotebookUtils credentials](https://learn.microsoft.com/fabric/data-engineering/notebookutils/notebookutils-credentials) | storage token、実行 identity の注意、SDK credential の利用／3・7章 |

## Foundry

| ID | Microsoft Learn | 確認した内容／ガイド |
|---|---|---|
| A1 | [Agent networking options](https://learn.microsoft.com/azure/foundry/agents/concepts/networking-options) | Prompt／Hosted 両方、inbound と egress の別、BYO／Managed、作成時設定／0・4章 |
| A2 | [Private Link / network isolation](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link) | 入口 PE、Portal の BYO injection、tool support／Public tools の区別／4・5章 |
| A3 | [Managed VNet](https://learn.microsoft.com/azure/foundry/how-to/managed-virtual-network) | 新 Agent Service 両タイプ対応、CLI 2.86.0、Portal 作成非対応、2026-05-01 API、承認ロール、PE rules／4章 |
| A4 | [MCP tool connection](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol) | Private MCP、project connection の認証保存、approval／5章 |
| A5 | [Hosted deployment](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent) | ContainerConfiguration、Responses protocol、version、active、ACR permissions／6章 |
| A6 | [Hosted quickstart](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-hosted-agent) | Python SDK／Project endpoint、実行の流れ／6章 |
| A7 | [Hosted permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions) | Project／Account／Agent identity の区別、外部データ RBAC／2・6章 |
| A8 | [Agent Framework Foundry hosting](https://learn.microsoft.com/agent-framework/hosting/foundry-hosted-agent) | ResponsesHostServer による自作コンテナのプロトコル／6章 |
| A9 | [Agent identity](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-identity) | identity の確認・アクセスの考え方／6章 |

## データとネットワーク

| ID | Microsoft Learn | 確認した内容／ガイド |
|---|---|---|
| D1 | [PostgreSQL Private Endpoint](https://learn.microsoft.com/azure/postgresql/network/how-to-networking-servers-deployed-public-access-add-private-endpoint) | Public mode + PE、Private VNet injection と区別／2章 |
| D2 | [PostgreSQL Entra roles](https://learn.microsoft.com/azure/postgresql/security/security-manage-entra-users) | service principal oid と DB role の登録、pgaadauth 関数／2章 |
| D3 | [Azure Files OAuth over REST](https://learn.microsoft.com/azure/storage/files/authorize-oauth-rest) | backup intent、Privileged Reader、API version、fileshares scope、classic の対象／7章 |
| D4 | [Prevent Shared Key authorization](https://learn.microsoft.com/azure/storage/common/shared-key-authorization-prevent) | false 設定の意味、Files SMB を同一視しない／2・7章 |
| D5 | [Private Endpoint DNS zones](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) | Storage、Foundry、PG 等の DNS zone／1章 |
| D6 | [Container Apps PE](https://learn.microsoft.com/azure/container-apps/how-to-use-private-endpoint) | workload profiles、Public Disabled、managedEnvironments target、DNS／5章 |
| D7 | [Container Apps custom VNet](https://learn.microsoft.com/azure/container-apps/custom-virtual-networks) | 専用 subnet／ネットワーク設計／1・5章 |
| D8 | [PostgreSQL TLS](https://learn.microsoft.com/azure/postgresql/security/security-tls) | verify-full／ルート証明書／2章 |
| D9 | [ACR role modes](https://learn.microsoft.com/azure/container-registry/container-registry-rbac-built-in-roles-overview) | AcrPull/AcrPush と Repository Reader/Writer の区別／5・6章 |
| D10 | [Get Blob REST](https://learn.microsoft.com/rest/api/storageservices/get-blob) | OAuth 読み取り、date／version header／共通プローブ |
| D11 | [Get File REST](https://learn.microsoft.com/rest/api/storageservices/get-file) | date／version／backup intent header／Files プローブ |

## Microsoft の公開サンプル

Learn のネットワーク選択表から参照される一次サンプルです。README と実装に差があれば **現行 Learn と実際のテンプレート実装を確認**し、古い比較表だけを根拠にしません。

| サンプル | 用途 |
|---|---|
| [11-private-network-basic-vnet](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet) | BYO Basic の参照。業務 Blob／PG と Agent 状態リソースを分ける |
| [15-private-network-standard-agent-setup](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup) | 状態データも BYO の Standard を求める場合 |
| [18-managed-virtual-network](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/18-managed-virtual-network) | Managed、Hosted tools の CAE PE／送信 PE 参照 |
| [19-private-network-agent-tools](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/19-private-network-agent-tools) | BYO の private tools／MCP 参照 |

このリポジトリは公式テンプレートを転載していません。使用する場合は Microsoft repository を clone し、その commit SHA、ライセンス、parameters、命名／Policy の差分を確認してから実行してください。Deploy to Azure を押すだけで本ラボの命名と既存 VNet に一致するとは限りません。

## 意図的なラボ上の選択

- Blob 主ルートは利用者との合意による変更。Files の証明は別ケース。
- Fabric 主手順は Dataflow Gen2 + VNet gateway。全 item を網羅する試験ではない。
- BYO は Basic。Agent 状態リソースすべてを自社所有にする試験ではない。
- Managed は approved-only。FQDN rule の自動 Firewall 費用を避け、PE rule を使う。
- MCP は検証専用 secret header。Storage は全て OAuth。本番認証は別途設計する。
- Hosted のデータ証跡は独自ツール。モデルの文章だけを成功としない。

## 更新時の確認

1. 特に F9、A1、A2、A3、A5 を再読し、Preview／対応表／API の変更を確認。
2. 新 Foundry／classic、Responses／Assistants のどの仕様かを必ず確認。
3. SDK を更新したらローカル import、コンテナ起動、閉域の正／負テストを再実施。
4. 更新履歴に確認日と実測対象のバージョンを残す。

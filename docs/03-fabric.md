# 3. Fabric の入口とデータ取得

[目次](../README.md) | [前](./02-data-sources.md) | [次](./04-foundry-network.md)

**この章は Azure Owner だけでは実施できません。Fabric administrator と workspace admin が必要です。**

## 3-1. Capacity と Workspace

1. Azure Portal → Microsoft Fabric → Create capacity。
2. 同 RG、名前 `capffnwtest`、対応リージョン、有料 F SKU。試験で十分な最小 SKU を見積もる。
3. Fabric 管理画面で capacity を利用できることを確認。
4. `ws-fabric-nwtest` を作成 → Workspace settings → License info / Capacity → この capacity を割り当てる。
5. Workspace 内で Lakehouse `lh_nwtest` を作成する。

Trial の Workspace を使うと、MPE が作れても **入口 Private Link の試験は成立しません**。有料 capacity への割り当てまで確認します。

## 3-2. Tenant Private Link を作る

本ガイドは公式の **Tenant-level Private Link** 手順を使います。Workspace-level もありますが、両方を混ぜず、まず Tenant-level だけで試します。

1. Fabric → OneLake catalog → Govern → Configurations → Tenant settings（表示が異なる場合は Admin portal → Tenant settings）。
2. **Azure Private Link = Enabled**。
3. 約 15 分待つ。**まだ Block Public Internet Access は有効にしない。**入口が完成してから遮断します。
4. Azure Portal → Deploy a custom template → Build your own template in the editor。
5. [公式 Step 2](https://learn.microsoft.com/fabric/security/security-private-links-use#step-2-create-a-microsoftpowerbi-private-link-services-for-power-bi-resource-in-the-azure-portal) の ARM JSON を貼る。
6. `<resource-name>` を `fabric-pls-nwtest`、`<tenant-object-id>` を自分の Entra tenant ID に置換。
7. 種類は **`Microsoft.PowerBI/privateLinkServicesForPowerBI`**、API は公式掲載の `2020-06-01`、location は Azure Public Cloud では `global`。名前が PowerBI でも Fabric 用です。
8. Deployment の RG は **既存の `rg-fabric-foundry-nwtest`** を選ぶ。公式例の別 RG を作らない。
9. Private endpoints → Create → `pep-fabric-tenant`、同 RG／Region。
10. Resource type: `Microsoft.PowerBI/privateLinkServicesForPowerBI`、Resource: `fabric-pls-nwtest`、target subresource: **`Tenant`**。
11. VNet／Subnet: `vnet-fabric-foundry-lab`／`subnet-pe`。
12. Private DNS integration = Yes。3 つの Fabric zone を同 VNet にリンクする。
13. Create → Approved を確認。

Fabric PE は capacity 数に応じ複数 IP を使います。公式は **capacity 数 + 15** の IP を見込むよう説明しています。`subnet-pe` の /24 は小規模ラボ用の余裕です。

## 3-3. 入口の確認 → 公開入口を閉じる

VM 内 PowerShell:

```powershell
nslookup <tenant-idからハイフンを除いた文字列>-api.privatelink.analysis.windows.net
```

1. Private IP が返ることを PE の DNS configuration と照合。
2. VM 内ブラウザーで `https://app.fabric.microsoft.com` を開く。
3. Workspace と Lakehouse を開けることを確認。
4. ブラウザー Developer Tools → Network で実際のデータ API の Host を確認。必要に応じその FQDN も DNS 解決する。
5. Fabric 管理者 → Tenant settings → **Block Public Internet Access = Enabled**。
6. 約 15 分待ち、VM 内で Workspace／Lakehouse の実データ操作が引き続き成功することを確認。
7. VNet 外の PC から同じ Workspace の実データ操作が拒否されることを確認。

Portal の HTML が開くだけでは入口試験の合格にしません。容量作成後に Private DNS へ反映されるまで **最大 24 時間**かかる場合があります。Unsupported item は遮断後に無効になるため、[公式 workload 制限](https://learn.microsoft.com/fabric/security/security-private-links-overview)を確認します。

## 3-4. VNet data gateway を作る

Fabric の Dataflow／Copy の実行ネットワークは、自分のブラウザーの VNet ではありません。gateway を通して VNet のデータソースへ到達させます。

1. Subscription の `Microsoft.PowerPlatform` Provider を Register。
2. VNet → Subnets → `subnet-fabric-gateway` → Delegation が **`Microsoft.PowerPlatform/vnetaccesslinks`**であることを確認。
3. Fabric / Power BI の歯車 → **Manage connections and gateways**。
4. **Virtual network data gateways → New**。
5. Capacity、Subscription、RG `rg-fabric-foundry-nwtest`、VNet、`subnet-fabric-gateway` を選択。
6. 名前 `gw-vnet-nwtest`、Save。利用可能状態になるまで待つ。

これは VPN Gateway ではありません。オンプレ用 gateway を VM にインストールする手順とも別です。Fabric Private Link 有効時は on-premises data gateway に制限があり、本ラボは **VNet data gateway** を使います。

根拠: [VNet gateway 作成](https://learn.microsoft.com/data-integration/vnet/create-data-gateways)。

## 3-5. Dataflow Gen2 から Blob を読む

まず公式に VNet gateway と Fabric Private Link の併用が明記された Dataflow Gen2 で確認します。

1. Manage connections and gateways → Connections → New。
2. 接続種類 Azure Blob Storage、接続名 `conn-blob-private`。
3. VNet gateway `gw-vnet-nwtest` を選ぶ。**None / Cloud の直接接続を選ばない**。
4. URL / Account に `https://stffnw<suffix>.blob.core.windows.net`。
5. Authentication = **Organizational account**、Blob Data Reader を持つ検証ユーザーで Sign in。
6. Privacy level は組織のルールに合わせる（ラボは Organizational）。
7. Create／Test connection が成功することを確認。Account key／SAS／Anonymous を選ばない。
8. Workspace → New item → Dataflow Gen2 → Get data → Azure Blob Storage。
9. 作成済み connection を選び、`labdata/marker.txt` を選択。
10. Transform data → 一行テキストをテーブルに変換、列名を `marker` にする。必要に応じ Text/CSV として開く。
11. Add data destination → Lakehouse `lh_nwtest`、テーブル `blob_marker` → Publish → Refresh。
12. Lakehouse のテーブルを開き、最新 marker を確認。Refresh history の成功時刻を記録。

根拠: [Blob connector capabilities](https://learn.microsoft.com/fabric/data-factory/connector-azure-blob-storage-overview)、[接続手順](https://learn.microsoft.com/fabric/data-factory/connector-azure-blob-storage)。

## 3-6. Dataflow Gen2 から PostgreSQL を読む

Dataflow Gen2 では **PostgreSQL database** コネクタを使います。Pipeline 用 **Azure Database for PostgreSQL** と名称／機能表を混同しないでください。

1. Manage connections and gateways → New → PostgreSQL database。
2. `conn-postgres-private`、gateway `gw-vnet-nwtest`。
3. Server = 通常の `pg-ffnw-<suffix>.postgres.database.azure.com`、Database = `labdb`。
4. Authentication = Basic、User = `fabric_reader`、DB の固有パスワードを入力。Encrypted connection / SSL を有効にする。
5. Test connection 成功を確認。
6. 新しい Dataflow Gen2 → Get data → PostgreSQL database → この接続を選択。
7. `public.lab_marker` を選び、Lakehouse `lh_nwtest` の `postgres_marker` に出力。
8. Publish → Refresh。最新 marker を確認。

根拠: [PostgreSQL database capabilities](https://learn.microsoft.com/fabric/data-factory/connector-postgresql-overview)。Azure Database for PostgreSQL の Pipeline コネクタも VNet gateway と Basic をサポートしますが、この主手順は Dataflow Gen2 です。

## 3-7. Notebook から Blob を読む（MPE の実測用）

gateway の内部 DNS を VM から観測しただけでは gateway そのものの DNS を証明できません。補助試験として、実行場所から DNS と実データを一緒に出せる Notebook も使います。

1. Workspace settings → **Network security → Managed private endpoints → Create**。
2. 名前 `pep-fabric-blob`、Resource ID = Storage account の完全な ARM ID、target subresource = **`blob`**。
3. Storage account → Networking → Private endpoint connections → Fabric から来た要求を Approve。
4. Fabric 側で Approved / 接続準備完了を確認。既存 Notebook のセッションを停止し、新しいセッションで試す。
5. New item → Notebook（Spark notebook）、Lakehouse を添付する。
6. [network_probe.py](../samples/network_probe.py)を Lakehouse の `Files/lab/` に Upload。
7. [fabric_notebook.py](../samples/fabric_notebook.py) をセルへ貼り、Storage 名と marker を置換。
8. 実行。DNS の Private IP、HTTPS 読み取り、最新 marker が同じ結果に現れる。

`notebookutils.credentials.getToken("storage")` は Notebook の実行 ID の token です。まず **対話実行ユーザー**で試し、スケジュール／Pipeline へ変更するときはその実行 ID を再確認し RBAC と試験をやり直します。

MPE の名前を接続 URL に使うのではなく、通常の Storage FQDN を使います。自分の `pep-data-blob` を作っただけでは Notebook から使えません。

## 3-8. 負テスト

- 外部 PC: Fabric Workspace のデータアクセスが拒否される。
- Blob と PostgreSQL の Public Network Access が Disabled のまま Dataflow refresh が成功する。
- `gw-vnet-nwtest` を使わない別接続で同じデータアクセスを試すと、公開側で失敗する（既存接続を壊さず、試験用の別接続で行う）。
- Notebook: 専用試験 Workspace の MPE を未承認にした状態では取得に失敗し、承認後に成功する。削除／再作成は再作成待機時間の制限があるため乱用しない。

結果は [検証章](./08-validation.md) に記録します。VNet gateway の公式 Download diagnostics は Fabric Private Link に制限があるため、証跡をそれだけに依存させません。

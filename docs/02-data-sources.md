# 2. Blob と PostgreSQL を閉域化する

[目次](../README.md) | [前](./01-prerequisites-network.md) | [次](./03-fabric.md)

## 2-1. Blob を作成する

1. Portal → Storage accounts → Create。
2. RG `rg-fabric-foundry-nwtest`、名前 `stffnw<suffix>`、Region Japan East、Standard、LRS。
3. Advanced → Hierarchical namespace = Off（通常の Blob）。Allow Blob anonymous access = Off。
4. **Allow storage account key access = Disabled**。既存 Policy が強制していても解除しない。
5. Networking → Public network access = Disabled。
6. Private Endpoint を追加: `pep-data-blob`、VNet `vnet-fabric-foundry-lab`、`subnet-pe`、target subresource **`blob`**、Private DNS integration = Yes。
7. Review + create → Create。Networking → Private endpoint connections → Approved を確認。
8. 必要なら PE の NIC / DNS configuration で Private IP を控える。

> `allowSharedKeyAccess=false` は共有キーを使わない設計の設定／証跡ですが、Azure Files の SMB キー使用禁止をそれだけで保証する、と解釈してはいけません。[Files の注意](./07-azure-files.md)を参照してください。

### Entra 権限を付ける

Storage → Access control (IAM) → Add role assignment。

- 試験データを作る検証ユーザー: **Storage Blob Data Contributor**。
- 読むだけの Fabric ユーザー: **Storage Blob Data Reader**。
- 後で作る `id-mcp-reader` と Hosted Agent identity: **Storage Blob Data Reader**。

読み取りは可能なら container scope に限定。Portal で IAM を付けられることと Blob データの権限があることは別です。権限反映を数分待ちます。

### Private 側から試験データを入れる

VM 内ブラウザーで Portal → Storage → Storage browser。**認証方法を Microsoft Entra user account に切り替える**。キーへ切り替えない。

1. Blob containers → `labdata` を作成、匿名アクセス無効。
2. ローカルに `marker.txt` を作り、例として `lab-20261008-001` と一行だけ書く。
3. Upload で `labdata/marker.txt` を登録。
4. 実験ごとに新しい文字列に更新する。これを **nonce / marker** と呼び、古いキャッシュやモデルの推測を除外します。

VM で確認:

```powershell
Resolve-DnsName stffnw<suffix>.blob.core.windows.net
Test-NetConnection stffnw<suffix>.blob.core.windows.net -Port 443
```

期待: `pep-data-blob` の IP、TCP 443 成功。DNS 成功だけではデータ取得成功とは判定しません。

## 2-2. PostgreSQL Flexible Server を作る

Azure Database for PostgreSQL **Flexible Server** を使います。Single Server は使いません。

1. Portal → Azure Database for PostgreSQL flexible servers → Create。
2. 同 RG／Region、名前 `pg-ffnw-<suffix>`、小規模検証用の対応 SKU、HA はラボでは無効。
3. 認証は **PostgreSQL and Microsoft Entra authentication**。Entra administrator に自分または承認済み管理者を設定。
4. Networking では **Public access (allowed IP addresses) and private endpoint** 系の方式を選ぶ。
5. **Allow public access を無効**にし、Public firewall に `0.0.0.0` や自分の PC の許可ルールを追加しない。
6. PE `pep-data-postgres` を同 VNet／`subnet-pe` に作成。target subresource **`postgresqlServer`**、Private DNS integration = Yes。
7. Review + create → Create、PE Approved を確認。

**名前に “Public access” とある作成モードでも、Private Endpoint を作って Public Network Access を無効化できます。**これは “Private access (VNet Integration)” の delegated PostgreSQL subnet 方式とは別です。本ラボは Fabric／Foundry Managed から MPE を作るため、**Private Link / PE 方式**に統一します。既存の VNet-injected サーバーへそのまま PE を追加できると思わないでください。

根拠: [PostgreSQL PE 作成](https://learn.microsoft.com/azure/postgresql/network/how-to-networking-servers-deployed-public-access-add-private-endpoint)。

## 2-3. DB と読み取りユーザー

VM に `psql` を入れ、Portal が表示する **通常の FQDN** `pg-ffnw-<suffix>.postgres.database.azure.com` を使います。TLS は `sslmode=verify-full`、信頼するルート証明書を指定。Linux は一般に `/etc/ssl/certs/ca-certificates.crt` を利用できます。Windows は [Azure PostgreSQL TLS ガイド](https://learn.microsoft.com/azure/postgresql/security/security-tls) に従い CA bundle を用意します。

1. PostgreSQL 管理者として Private 側から接続し、`labdb` を作る。
2. `labdb` に接続し [seed.sql](../samples/seed.sql) を実行。
3. `fabric_reader` という DB ユーザーを作り、十分長い固有パスワードを設定。履歴にパスワードを残さないよう `psql` の `\password fabric_reader` 等を使う。
4. `GRANT CONNECT ON DATABASE labdb TO fabric_reader;`
5. `GRANT USAGE ON SCHEMA public TO fabric_reader;`
6. `GRANT SELECT ON TABLE public.lab_marker TO fabric_reader;`
7. Fabric の接続には、この読み取り専用 Basic ユーザーを使う。Storage Key 禁止と DB パスワードの禁止は別の条件です。DB パスワードも禁止ならこのコネクタ実験を止め、別の認証対応経路を検討します。

`seed.sql` の marker を Blob の `marker.txt` と同じ値に変更してください。

### Foundry / MCP は Entra token で DB に接続する

Entra administrator として、**`postgres` データベース**に接続して以下を実行します。Entra オブジェクトの **Object / Principal ID** を使い、Application / Client ID と混同しないでください。

```sql
SELECT * FROM pg_catalog.pgaadauth_create_principal_with_oid(
  'mcp_reader', '<id-mcp-reader の principal ID>', 'service', false, false);
```

続いて `labdb` に接続:

```sql
GRANT CONNECT ON DATABASE labdb TO mcp_reader;
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON TABLE public.lab_marker TO mcp_reader;
```

Hosted Agent を作成した後、Agent identity ごとに同様に作成:

```sql
SELECT * FROM pg_catalog.pgaadauth_create_principal_with_oid(
  'hosted_byo_reader', '<BYO Hosted の Agent principal ID>', 'service', false, false);
SELECT * FROM pg_catalog.pgaadauth_create_principal_with_oid(
  'hosted_managed_reader', '<Managed Hosted の Agent principal ID>', 'service', false, false);
```

それぞれ `labdb` で上記の CONNECT / USAGE / SELECT を付与します。Azure RG の Contributor を付けても DB の SELECT は許可されません。

Entra token の scope は `https://ossrdbms-aad.database.windows.net/.default`。サンプルではその token を DB password フィールドに渡します。token は毎回取得し、保存しません。

根拠: [Entra DB roles](https://learn.microsoft.com/azure/postgresql/security/security-manage-entra-users)。

## 2-4. 接続確認と公開遮断の確認

VM:

```powershell
Resolve-DnsName pg-ffnw-<suffix>.postgres.database.azure.com
Test-NetConnection pg-ffnw-<suffix>.postgres.database.azure.com -Port 5432
```

期待: PE の IP、TCP 5432 成功。

さらに認証して `SELECT id, marker FROM public.lab_marker;` の最新 marker を確認します。

VNet 外の PC から同じデータ読み取りを試験し、公開経由では失敗することを確認します。**外側で DNS が Public IP を返すこと自体は異常ではありません。**Private DNS zone は外側には効きません。403／接続拒否等を記録します。認証情報が間違っているだけの失敗はネットワーク遮断の証明にしないでください。

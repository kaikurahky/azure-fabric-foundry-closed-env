# 7. Azure Files: 制約とキーなし追加検証

[目次](../README.md) | [前](./06-hosted-agent.md) | [次](./08-validation.md)

## 7-1. Blob の検証と別にする理由

Blob と Files は同じ Storage account に作れますが、プロトコル、認証、PE の subresource が違います。

| 項目 | Blob | Azure Files |
|---|---|---|
| FQDN | `...blob.core.windows.net` | `...file.core.windows.net` |
| PE target | `blob` | `file` |
| 本ラボの読み取り | Blob REST + OAuth | FileREST + OAuth |
| Port | HTTPS 443 | 本ラボは HTTPS 443。SMB の 445 は使わない |
| RBAC | Blob Data Reader | **Storage File Data Privileged Reader** |
| Fabric 標準コネクタ | キーなし方式あり | 現行 Fabric Azure Files は **Account key のみ** |

[Fabric Azure Files capabilities](https://learn.microsoft.com/fabric/data-factory/connector-azure-files-overview) の現行表では、Pipeline／Copy job は gateway を使えますが認証は Account key です。**gateway を Private にしても認証非対応は解決しません。**

Azure Data Factory の Azure Files コネクタの記事に Managed Identity が載っていても、それを **Fabric Data Factory が対応済み**という根拠にしないでください。

## 7-2. 本章で検証するもの／しないもの

検証するもの:

- Classic Azure Files（`Microsoft.Storage/storageAccounts` 配下）。
- Fabric Notebook の `file` MPE + 対話ユーザー OAuth。
- MCP コンテナ／Hosted コンテナの `file` PE / MPE + Entra identity。
- Storage Access Key／SAS を一切使わない読み取り。

検証しないもの:

- SMB ドライブマウント、Kerberos、AD DS／Entra Domain Services／Entra Kerberos。
- 新 `Microsoft.FileShares` resource provider の File Shares。
- Fabric 標準 Azure Files コネクタをキーなしで動かすこと（現行認証制約）。

FileREST の OAuth は API **2022-11-02 以降**でデータ操作対応です。`x-ms-file-request-intent: backup` と backup semantics を含むデータ権限が必要。SMB Share Reader を付けるだけでは足りません。

**Privileged Reader はファイル／ディレクトリ ACL を越える読み取り権限**です。検証用 share に scope を絞り、顧客の本番 share に無条件に付けないでください。

## 7-3. File share と PE

1. [データ Storage](./02-data-sources.md)で File shares → `labfiles` を作る。classic SMB share、検証用の小さい quota。
2. customer VNet 向け PE **`pep-data-file`**を追加、target **`file`**、`subnet-pe`、`privatelink.file.core.windows.net` と VNet link。
3. Fabric workspace MPE **`pep-fabric-file`**を追加、同 Storage ARM ID、target **`file`**。Storage 側で Approve。
4. Foundry Managed outbound rule **`pep-managed-file`**を追加、同 Storage ARM ID、target **`file`**。接続承認を確認。
5. Blob の PE を Files に流用しない。

## 7-4. データ投入と権限

Storage File Data Privileged Contributor を、試験データを書き込むユーザーに検証期間だけ付与します。Portal に必要な管理 plane 権限も別途必要です。

読み取り:

- Fabric Notebook 対話実行ユーザー。
- `id-mcp-reader`。
- BYO／Managed の Hosted Agent identity。

に **Storage File Data Privileged Reader**。

share に絞る RBAC scope は以下の形です（Learn の注意どおり、RBAC scope は `shares` でなく **`fileshares`**）。

```text
/subscriptions/<sub>/resourceGroups/rg-fabric-foundry-nwtest/providers/Microsoft.Storage/storageAccounts/<storage>/fileServices/default/fileshares/labfiles
```

反映を待ち、VM 内 Portal の Storage browser で **Microsoft Entra account** に切り替え、`labfiles/marker.txt` を Upload。Blob／DB と同じ marker を使います。キーへの切り替えを要求される UI しかない場合は、Policy を解除せず [公式 OAuth over REST の CLI／PowerShell 手順](https://learn.microsoft.com/azure/storage/files/authorize-oauth-rest#authorize-access-by-using-the-filerest-data-plane-api)を使います。

### キー禁止の重要な注意

`allowSharedKeyAccess=false` による制御は Blob／Queue 等と Azure Files SMB で同じ動きとは限りません。[Prevent Shared Key authorization](https://learn.microsoft.com/azure/storage/common/shared-key-authorization-prevent)の “Azure Files” 注意を確認してください。

したがって「このフラグが false だから Files のキー使用が全面的に防止済み」とは説明しません。本ラボでは **キーを取得しない・配布しない・使用しない**、OAuth の identity／RBAC と認証ログを確認します。組織の Policy が何を deny／audit するかは管理者と確認します。

## 7-5. Fabric Notebook

1. `pep-fabric-file` が Approved、Public Network Access が Disabled を確認。
2. Notebook の実行セッションを再作成する。
3. [Notebook セル](../samples/fabric_notebook.py)の `INCLUDE_FILES = True`。
4. 最新の Storage 名／marker を設定して実行。
5. `files.host`、Private `resolved_ips`、marker を確認。

`getToken("storage")` を FileREST に使い、追加 header を [プローブ](../samples/network_probe.py)が付けます。トークン本文は表示しません。Blob 認証の機能を根拠に Files の標準コネクタ対応を主張しているのではなく、**一般の Storage OAuth token を FileREST で実測**する試験です。

## 7-6. Prompt Agent

1. MCP の UAMI に File Privileged Reader。
2. `pep-data-file` が Approved、MCP コンテナから File FQDN が Private IP に解決されることを確認。
3. Prompt の Allowed tools に **`read_private_marker_with_files`**を追加。
4. BYO と Managed の両 Prompt に、この tool の呼び出しを要求し Approve。
5. Tool trace と MCP log に Blob／PostgreSQL／Files の marker と Private IP。

この場合も Files への接続元は **MCP コンテナ**です。Foundry Managed の `pep-managed-file` はこのツールの後半には使われません。

## 7-7. Hosted Agent

1. Agent identity に File Privileged Reader。
2. BYO は `pep-data-file`、Managed は `pep-managed-file` の Approved 状態。
3. Playground／呼び出しスクリプトの入力を「`read_private_marker_with_files` を今呼んで JSON を返す」に変更。
4. Hosted ログで `Hosted data probe with Files` と 3 データソースの実データを確認。

## 7-8. よくある失敗

| 症状 | 確認 |
|---|---|
| Blob 成功、Files 失敗 | `file` PE／MPE が別にあるか |
| 403 | Privileged Reader と backup semantics、実際の実行 ID |
| AuthorizationFailure | role scope の `fileshares`、RBAC 反映、Public Network Access／DNS |
| 445 接続できない | 本章は FileREST 443。SMB を試験していない |
| ACL を無視して読めた | OAuth Privileged Reader の意図された仕様。検証 scope を確認 |
| Fabric connection に MI の選択肢がない | 標準 Azure Files connector の現行制約。キーを有効にしない |

根拠: [Files OAuth](https://learn.microsoft.com/azure/storage/files/authorize-oauth-rest)、[Fabric MPE supported data sources](https://learn.microsoft.com/fabric/security/security-managed-private-endpoints-create#supported-data-sources)。

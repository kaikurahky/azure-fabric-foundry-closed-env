# 9. トラブルシュートと片付け

[目次](../README.md) | [前](./08-validation.md) | [公式資料](./10-sources.md)

## 9-1. いつもこの順で確認する

1. **実行場所**: 自分の PC、VM、Fabric、MCP、Hosted のどれか。
2. **FQDN**: 通常の正しい FQDN を使っているか。
3. **DNS**: その実行場所で Private IP か。
4. **経路**: PE／MPE／委任／NSG／UDR／proxy。
5. **TLS**: Host name、CA trust、DB の verify-full。
6. **認証**: どの ID の token か。
7. **認可**: Blob／Files の RBAC、DB の SELECT、MCP connection。
8. **実データ**: marker を更新したか、該当 ID が存在するか。

Public access を有効にして一時的に「動く」状態へ変えてしまうと、閉域の根本原因が見えなくなります。やむを得ない比較実験でも承認を取り、変更前後を記録し、元に戻して最終試験を行います。

## 9-2. 症状別

| 症状 | 原因候補と操作 |
|---|---|
| VM から Public IP に解決 | PE の DNS configuration、zone の VNet link、同名 zone の重複、VM DNS cache |
| VM は成功、Notebook は失敗 | VM 用 PE は Notebook の MPE ではない。Fabric MPE を作り承認 |
| VM は成功、Managed Hosted は失敗 | Managed outbound rule がない／Pending／target subresource 違い |
| Blob 成功、DB timeout | PG PE mode、group ID、5432、NSG／UDR、PG Public Access の設定 |
| DB password authentication failed | Entra role の oid、PGUSER、token scope、Basic と Entra の混同 |
| Blob 403 | 実行 ID に Blob Data Reader がない、Public経路、role propagation |
| Files 403 | Privileged Reader、backup header、file PE、RBAC の fileshares scope |
| MCP 401 | `x-lab-tool-token` が違う、Foundry connection が別 Project |
| MCP 404 | endpoint が `/mcp` か、app FQDN／revision／target port 8000 |
| MCP session / transport error | Streamable HTTP のバージョン／host 検証／ロードバランサー設定。接続 trace とログを確認 |
| CA image pull failed | ACR PE、data endpoint DNS、MI 割当、Reader/AcrPull、role mode |
| Hosted active だが tool 失敗 | active はデータ権限の保証ではない。Agent identity の RBAC／DB role |
| Hosted model access failure | Project endpoint、deployment name、Project MI／Agent の model permission |
| Foundry 入口 403 / PublicNetworkAccessDisabled | CLI／SDK を実行している場所が VNet 外。VM 内へ移動 |
| Managed CLI が存在しない | Azure CLI バージョン／preview command group／公式 API を確認 |
| Fabric の Trial が開けない | inbound Private Link は Trial 非対応。有料 capacity を利用 |
| 新 capacity の endpoint がない | Private DNS 更新は最大 24 時間を考慮 |
| Fabric の gateway が見えない | PowerPlatform 委任、Provider、join/action、gateway region、capacity |
| Dataflow は成功、Pipeline で Warehouse copy が失敗 | Fabric Private Link の workload 制限。Lakehouse を使う本手順へ戻る |
| Portal は表示されるが実操作で失敗 | 静的 UI とデータ API は別。API FQDN／Private DNS／公開遮断の対象を確認 |

MCP ライブラリの DNS rebinding 保護により、custom FQDN が拒否される場合があります。**保護を全面無効化して回避せず**、実際の MCP app FQDN を allow-list に設定し、ライブラリの提供 API と照合してください。

## 9-3. DNS キャッシュ／NSG

VM の PowerShell:

```powershell
ipconfig /flushdns
Resolve-DnsName <通常のservice FQDN>
Test-NetConnection <通常のservice FQDN> -Port 443
```

Notebook は既存セッションを止め、Hosted／MCP は新 revision／session で再試験。NSG は通信元 subnet と PE の Private IP／必要 port を確認。単なる `Allow Internet` で代用しません。

Foundry BYO の委任 subnet にはプラットフォーム依存の制約があるため、検証初期に UDR／NSG の一括 Deny All を追加しないでください。必要な許可は [公式 Foundry network requirements](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link)を読み、ラボ成功後に段階的に制限します。

## 9-4. 作成をやり直すとき

Foundry の方式変更を上書き更新で試さず、別 account／project と必要なら別 delegated subnet を作ります。subnet のサービス関連付けが残る場合があります。

Fabric MPE の削除後、同じ target に再作成するには公式の待機時間（少なくとも 15 分）を守ります。実験用に共有データ PE を削除して全ケースを壊さないでください。

Policy の `Deny` はネットワーク障害ではありません。Deployment error の policy assignment を記録し、管理者へ用途・必要設定を説明します。Policy を勝手に除外しません。

## 9-5. 片付け前チェック

**以下はユーザーが検証後に実行する手順です。本ガイド作成時には実行していません。**

1. private 証跡の必要なものを保存し、機密情報をマスク。
2. Fabric Tenant settings の変更前状態を確認。
3. テナント全体の Private Link／Block Public Internet Access を、承認された元の状態へ戻す。既存の他の PE／業務利用がある場合は無条件に無効化しない。
4. Fabric Workspace の Notebook／Dataflow／接続／MPE と VNet data gateway を削除／停止する。これらは Azure RG の削除だけでは全て消えません。
5. Fabric Workspace の capacity 割当を解除し、検証 workspace を削除する。
6. Hosted の versions／sessions／Prompt Agent を不要なら削除。Hosted active session の課金停止を確認。
7. 検証用 RBAC、MCP token、DB roles、Entra app／Agent identity 関連を確認し、検証専用のものだけを整理。
8. Fabric capacity を pause／delete する。VM だけ停止しても capacity は止まりません。

最後に RG 内を確認:

```bash
az resource list -g rg-fabric-foundry-nwtest -o table
```

検証用だけであることを目視確認し、承認を取ってから Portal → RG → **Delete resource group**。確認欄に `rg-fabric-foundry-nwtest` を入力して削除。

CLI を使う場合も対象はこの RG だけです。実行すると内側のデータが失われます:

```bash
az group delete --name rg-fabric-foundry-nwtest
```

削除状態／依存エラーを確認し、Cost Management で残存課金を確認。Managed Foundry の削除は managed network の削除につながりますが、他のサービスの共有リソースまで自動で消えると思わないでください。

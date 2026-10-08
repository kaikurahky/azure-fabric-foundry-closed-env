# 8. 合否判定とお客様説明用の証跡

[目次](../README.md) | [前](./07-azure-files.md) | [次](./09-troubleshooting-cleanup.md)

## 8-1. 合格は 4 点セット

1. **設定**: Public Network Access Disabled、目的の PE／MPE Approved。
2. **名前解決／経路**: 実際の実行場所で宛先 FQDN が Private IP。PE target／subresource も正しい。
3. **実データ**: 認証・認可を通り、最新 nonce / marker の取得が成功。
4. **負テスト**: 閉域外から公開経由で同じ操作は拒否される。

Private IP の `nslookup` だけ、TCP の接続だけ、モデルの回答だけでは未合格です。

## 8-2. 最初に設定一覧を保存する

管理 API はデータ用 PE を経由する API とは違います。外部 PC から `az resource show` が成功しても、データプレーンが公開されている証拠ではありません。

```bash
az resource list -g rg-fabric-foundry-nwtest \
  --query '[].{name:name,type:type,location:location}' -o table

az storage account show -g rg-fabric-foundry-nwtest -n "<storage>" \
  --query '{publicNetworkAccess:publicNetworkAccess,allowSharedKeyAccess:allowSharedKeyAccess}' -o json

az cognitiveservices account show -g rg-fabric-foundry-nwtest -n "<account>" \
  --query 'properties.{publicNetworkAccess:publicNetworkAccess,networkInjections:networkInjections,privateEndpointConnections:privateEndpointConnections}' -o json

az network private-endpoint list -g rg-fabric-foundry-nwtest \
  --query '[].{name:name,connections:privateLinkServiceConnections}' -o json
```

PostgreSQL は Portal の Networking、Container Apps は **environment** の Public Network Access、Fabric は Tenant settings をスクリーンショットで保存します。MCP app の ingress 表示だけから environment の公開状態を判定しないでください。

## 8-3. 検証ケース

| ID | 実行場所 | 操作 | 期待 |
|---|---|---|---|
| IN-FAB | VM browser | Fabric Workspace／Lakehouse を開き実データ表示 | Private ingress で成功 |
| OUT-FAB-BLOB | Dataflow Gen2 | VNet gateway 経由 refresh | Blob 最新 marker |
| OUT-FAB-PG | Dataflow Gen2 | VNet gateway 経由 refresh | DB 最新 marker |
| OUT-NB-BLOB | Fabric Notebook | MPE + Storage OAuth | Private DNS＋Blob 最新 marker |
| IN-BYO | VM SDK | BYO Project の Agent 呼び出し | 認証付き実行成功 |
| IN-MANAGED | VM SDK | Managed Project の Agent 呼び出し | 認証付き実行成功 |
| P-BYO | Prompt / BYO | private MCP tool | 前半 PE、後半 PE、Blob／DB marker |
| P-MANAGED | Prompt / Managed | private MCP tool | 前半 MPE、後半 PE、Blob／DB marker |
| H-BYO | Hosted container | 直接 Blob／DB tool | container 内 Private DNS＋marker |
| H-MANAGED | Hosted container | 直接 Blob／DB tool | Managed MPE＋marker |
| FILE-NB | Fabric Notebook | OAuth FileREST | `file` MPE＋marker |
| FILE-P-BYO | BYO Prompt tool | MCP の FileREST | tool 側 PE＋marker |
| FILE-P-MANAGED | Managed Prompt tool | MCP の FileREST | 前半 MPE、tool 側 PE＋marker |
| FILE-H-BYO | BYO Hosted | FileREST | BYO PE＋marker |
| FILE-H-MANAGED | Managed Hosted | FileREST | Managed MPE＋marker |
| NEG-FAB | VNet 外 PC | Fabric データアクセス | 公開経由拒否 |
| NEG-BYO | VNet 外 PC | BYO Agent 呼び出し | 公開経由拒否 |
| NEG-MANAGED | VNet 外 PC | Managed Agent 呼び出し | 公開経由拒否 |
| NEG-BLOB-PG | VNet 外 PC | データ読み取り | 公開経由拒否 |
| NEG-FILES | VNet 外 PC | OAuth FileREST | 公開経由拒否 |
| NEG-MCP | VM / 外部 PC | token なし／公開接続 | 内部は 401、公開はネットワーク拒否 |

未実施、製品非対応、権限不足、地域非対応は **PASS ではなく NOT_RUN / UNSUPPORTED / BLOCKED** と記録します。Azure Files 標準コネクタのキーなし試験は `UNSUPPORTED`、Notebook／ツールの追加試験とは別です。

## 8-4. marker の運用

試験前に各ケース固有の marker を用意します（例 `lab-<日付>-<ケースID>-<ランダム文字列>`）。

1. Blob の `labdata/marker.txt` を更新。
2. DB の `lab_marker` を UPDATE。
3. Files を試すときは `labfiles/marker.txt` も更新。
4. Notebook／MCP／Hosted の `EXPECTED_MARKER` を一致させる。
5. Agent のプロンプトには marker を書かない。
6. 新しい実行／Hosted version で取得し、実行時刻・tool trace・ログを記録。

`check_marker()` は不一致を例外にします。データの更新忘れを成功扱いしません。

## 8-5. 経路の補強証拠

- customer PE: NIC Private IP と DNS の IP の照合。
- gateway: 接続定義の VNet gateway ID、Public Disabled のソースへの Refresh 成功。必要なら組織承認済みの network logs で補強。
- Fabric／Foundry MPE: resource ID、subresource、approval 状態、実行側の DNS／実データ。
- Prompt: Foundry tool trace に **private MCP URL** と tool invocation があること。MCP コンテナ側ログと時刻／marker を照合する。
- Hosted: Hosted logs にプローブの JSON があること。VM からの出力を Hosted の証拠に代用しない。

Managed 側には customer-visible NIC がなく、実行側の IP と customer PE の IP が一致しないことがあります。「NIC が見えない＝Public」と判定しません。

Network Watcher／フローログ／storage diagnostics は補助として使えますが、サービスによって記録可能範囲が違います。ログ不在だけで「通信していない」と結論しません。

## 8-6. トークンと証跡の安全な保存

[検証票](../evidence/results-template.csv) をコピーし、実測版は `evidence/private/` に保存します。このディレクトリは Git ignore 対象です。

記録:

- 日時、Azure region、tenant home region、capacity SKU。
- CLI／SDK／MCP／Agent Framework バージョン。
- Public Access 状態、PE／MPE の target と Approved 状態。
- 実行場所、実行 ID、Agent／revision／version／image digest。
- DNS、nonce、成功／エラーコード、tool trace の参照。

記録しない:

- token、Storage Access Key、DB password、MCP token。
- 本番データ、秘密鍵、非公開顧客情報。

JWT の全体を表示して ID を調べないでください。Portal の ID 情報と role assignment で実行 ID を確認します。

## 8-7. お客様へ説明する文例

```text
本検証では、Fabric と Foundry の対応データプレーンに Private Link を設定し、
公開アクセスを無効化しました。Blob と PostgreSQL の取得は、Fabric では
VNet gateway／Notebook MPE、Foundry では BYO／Managed の各実行経路で確認しました。

Prompt Agent は private MCP を呼び、データアクセスはツール側の VNet で行います。
Hosted Agent はコンテナ自身が BYO／Managed のネットワークから直接取得します。

Storage Access Key は使用していません。Azure Files は標準 Fabric コネクタの
キーなし認証が非対応のため、Notebook／ツールの OAuth FileREST で別に検証しました。

なお、管理 API、Entra ID サインイン、製品の静的 UI などまで Public 通信が
完全にゼロという確認ではありません。対象ワークロードと Preview の条件、
処理地域／データ所在地は別途確認が必要です。
```

実測が終わる前は、「確認しました」を「確認する計画です」に変えて説明してください。

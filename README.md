# Fabric / Microsoft Foundry 閉域構成ハンズオン

Azure 初心者が、自分の検証環境で **「入口が Private IP」「データ取得も Private IP」「Storage Access Key を使わない」** を確認するための日本語ガイドです。GitHub にこのディレクトリをそのままアップロードして利用できます。

> **公式資料の確認日: 2026-10-08。Azure 実機での構築・実行は未実施です。**
> 本ガイドは Microsoft Learn の本文と Microsoft の公開サンプルを照合して作成しました。サンプルの構文／ローカルテストと、Azure 上の動作確認は別物です。お客様に「検証済み」と説明する前に、[検証票](./evidence/results-template.csv)を実測で埋めてください。Preview、リージョン、ポータル表示、SDK は変更され得ます。

## 今回の合意と対象範囲

- 主ストレージを **通常の Azure Blob Storage** に変更します。ADLS Gen2／階層型名前空間は不要です。
- 元の Azure Files 要件は [追加検証](./docs/07-azure-files.md) に残します。Blob の成功は Files の成功を意味しません。
- RG は必ず `rg-fabric-foundry-nwtest`。VNet は `vnet-`、Subnet は `subnet-`、Private Endpoint／Managed Private Endpoint の自分で指定できる名前は `pep-`。
- Bastion 専用の **`AzureBastionSubnet` だけは承認済みの例外**です。Azure の予約名です。Microsoft 管理 VNet 内の自動生成リソース名／IP は指定できません。
- Azure Public Cloud、検証専用テナントまたは影響を承認されたテナントを対象にします。
- データプレーンの入口とデータ取得を閉域化します。Entra ID サインイン、Azure 管理 API、パッケージ取得、ポータルの静的コンテンツまで「一切 Public IP を使わない」構成ではありません。
- 本番品質の HA、DR、顧客データの使用、全通信の Firewall 検査、Foundry の全状態データを自社所有リソースに格納する構成は対象外です。

## 実施順序

| 順序 | 章 | できるようになること |
|---|---|---|
| 0 | [構成と用語](./docs/00-architecture.md) | 入口 PE と送信 VNet を混同しない |
| 1 | [準備・共通ネットワーク](./docs/01-prerequisites-network.md) | 権限、費用、命名、Bastion、VM、DNS |
| 2 | [Blob / PostgreSQL](./docs/02-data-sources.md) | 公開アクセスを止め、試験データと読み取り権限を用意 |
| 3 | [Fabric](./docs/03-fabric.md) | 入口 Private Link、VNet gateway、Notebook の MPE |
| 4 | [Foundry の入口と送信ネットワーク](./docs/04-foundry-network.md) | BYO VNet と Managed VNet を別アカウントで構築 |
| 5 | [Prompt Agent](./docs/05-prompt-agent.md) | private MCP を介したデータ取得を両方式で試験 |
| 6 | [Hosted Agent](./docs/06-hosted-agent.md) | コンテナ自身のデータ取得を両方式で試験 |
| 7 | [Azure Files 追加検証](./docs/07-azure-files.md) | OAuth / FileREST、標準コネクタの非対応を理解 |
| 8 | [合否判定・証跡](./docs/08-validation.md) | 実行場所、正／負テスト、実データをそろえる |
| 9 | [トラブル対応・片付け](./docs/09-troubleshooting-cleanup.md) | DNS／経路／認証を切り分け、費用を止める |
| 参考 | [公式資料と主張の対応](./docs/10-sources.md) | 各判断の根拠を Microsoft Learn で追跡 |
| 検証記録 | [ローカル検証結果](./docs/11-local-validation.md) | Azure 実測と区別したサンプル検査結果 |

**初めての方は 1 → 2 → Fabric → Foundry BYO → Foundry Managed の順**がおすすめです。同じデータソースを使いますが、実験結果は方式ごとに分けて記録します。

## 最終的な検証マトリクス

| 送信元 | Blob / PostgreSQL への主経路 | Azure Files |
|---|---|---|
| Fabric Dataflow Gen2 | VNet data gateway → データソース PE | 標準 Azure Files コネクタはキー前提なので採用しない |
| Fabric Notebook | Fabric managed network → MPE | `file` MPE → OAuth FileREST |
| Prompt / BYO | Foundry delegated subnet → MCP 環境 PE → MCP コンテナ → データソース PE | MCP コンテナから OAuth FileREST |
| Prompt / Managed | Foundry Managed VNet → MCP 環境 MPE → MCP コンテナ → データソース PE | 同上 |
| Hosted / BYO | Hosted コンテナ → BYO delegated subnet → データソース PE | コンテナから OAuth FileREST |
| Hosted / Managed | Hosted コンテナ → Managed VNet → データソース MPE | 同上 |

入口は、VM → Fabric の `pep-fabric-tenant`、VM → Foundry の `pep-foundry-byo`／`pep-foundry-managed` を別途検証します。

## リポジトリ内の補助資材

- [共通データプローブ](./samples/network_probe.py): DNS／接続／実データを同一実行場所から確認。トークンやパスワードは出力しません。
- [Notebook 用セル](./samples/fabric_notebook.py): Blob と Azure Files を OAuth で確認。
- [private MCP サーバー](./samples/mcp_server.py)と[コンテナ定義](./samples/Dockerfile.mcp)。
- [Hosted Agent](./samples/hosted_main.py)、[デプロイ](./samples/deploy_hosted.py)、[呼び出し](./samples/invoke_hosted.py)。
- [DB 初期化 SQL](./samples/seed.sql)、[ローカル単体テスト](./tests/test_network_probe.py)。
- [検証結果テンプレート](./evidence/results-template.csv)。

サンプルは検証用のオリジナル実装です。Microsoft がサポートする完成済みソリューションではありません。実機で成功したパッケージバージョン、モデル名、サンプルの commit SHA を必ず記録してください。[ローカル検証結果](./docs/11-local-validation.md)も参照してください。

## GitHub リポジトリ

公開リポジトリ: [kaikurahky/azure-fabric-foundry-closed-env](https://github.com/kaikurahky/azure-fabric-foundry-closed-env)

### 別リポジトリへ公開するとき

1. このディレクトリを VS Code で開く。
2. [`.gitignore`](./.gitignore) を確認し、`.env`、証明書の秘密鍵、API トークン、実測ログなどを除外する。
3. ソース管理で Initialize Repository → 内容を確認 → Commit → Publish to GitHub。
4. 実測証跡を共有する場合は、テナント ID、Subscription ID、ユーザー名、実リソース ID、データ内容をマスクする。スクリーンショットにも注意する。

管理者権限、Policy 変更、テナント全体の Public Access 遮断は、必ず組織の承認を取ってから実施してください。

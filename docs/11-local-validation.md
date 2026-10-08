# ローカル検証記録

[目次](../README.md) | [Azure 実測手順](./08-validation.md)

実施日: **2026-10-08**。この記録は Azure 上の閉域疎通成功を示すものではありません。

ローカル検査は Python 3.12 の隔離 venv で実施しました。Dockerfile の Python 3.11 コンテナ build は未実施であり、この差も Azure 実測前に確認が必要です。

## 実施したチェック

| チェック | 結果 |
|---|---|
| Markdown 内部リンク／コードフェンス | PASS |
| 検証 CSV の 22 ケース、重複なし、初期状態 NOT_RUN／UNSUPPORTED | PASS |
| Python 7 ファイルの構文 | PASS |
| DNS Private IP 判定、marker、空／Public混在 DNS、REST header／エラー伝播等の単体テスト | **13 tests PASS** |
| 共通／MCP／Hosted／deploy／invoke の runtime import | PASS |
| pip check による依存整合性 | PASS（No broken requirements found） |
| HostedAgentDefinition の作成／シリアライズ | PASS |
| MCP server のローカル起動と Initialize | PASS |
| MCP の 2 ツール discovery | PASS |
| MCP token なしのアクセス | **401** を確認 |
| MCP 未許可 Host のアクセス | **421** を確認 |
| Hosted protocol server のローカル起動 | PASS |
| Hosted `/readiness` | **200 / `{"status":"healthy"}`** を確認 |

localhost の試験ではダミー値を使用し、Azure 認証、モデル inference、実データアクセスは呼び出していません。試験サーバーは停止済みです。

MCP の初期既定 Host allow-list が localhost のみだったため、実際の Container App FQDN を `MCP_HOSTNAME` で追加する実装に修正し、未許可 Host の拒否も再確認しました。Hosted の default port はパッケージの実装に合わせて 8088 としています。

## 使用した主要パッケージ

| パッケージ | バージョン |
|---|---|
| azure-ai-projects | 2.7.0 |
| azure-identity | 1.26.0 |
| psycopg | 3.3.6 |
| mcp | 1.30.0 |
| uvicorn | 0.54.0 |
| agent-framework | 1.20.0 |
| agent-framework-foundry-hosting | 1.0.0b261002 |

このバージョンを requirements に固定しています。推移依存、Docker base image、Azure 側提供機能まで不変になるわけではありません。Azure 実測で成功した image digest と依存一覧をさらに記録してください。

## 再実行

単体テストは標準ライブラリだけで実行できます。

```bash
python3 -m unittest discover -s tests -v
```

Windows ではインストールした Python に合わせ `python` を使います。MCP／Hosted の起動確認にはそれぞれの requirements が必要です。Azure に接続する実測は [各ハンズオン章](../README.md) に従います。

## 未検証

- Azure リソースの作成／Policy／リージョン／Quota。
- Fabric／Foundry の Portal 実操作と入口／送信経路。
- Azure identity の token 取得、Blob／Files／PostgreSQL の実読取。
- Docker build／ACR push／Foundry Hosted の Azure deployment。
- 閉域外からの実際のアクセス拒否。

これらは [検証票](../evidence/results-template.csv) を埋めて初めて実機検証済みになります。

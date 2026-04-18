# order-automation-poc

製造業向けの受注カード管理 PoC です。  
FastAPI + OCR（Tesseract）で、受注ファイルの添付・OCR・調達項目抽出を行います。

現在は **ローカル構成** と **AWS構成（ECS/RDS/S3/SQS）** の両方に対応した実装です。

## 実装機能

### ボードUI
- 5ステータスのカンバン表示
- カード作成
- ドラッグ&ドロップでステータス更新
- カード詳細編集（受注番号、機械番号、型式、客先名、希望所要日数）
- 添付スロット 1〜6 へのファイルアップロード
- PDF/画像プレビュー
- OCR 再実行
- 調達項目抽出（部品番号、数量、材質、表面処理、候補供給先など）
- CSV 出力

### バックエンド
- 添付1（注文情報）アップロード時に OCR ジョブ投入
- OCR から受注項目抽出
- OCR から調達項目抽出
- 履歴を使った手配候補評価
- 自動化ログ保存
- OCR 非同期実行（API + worker 分離、SQS キュー）

## ステータス
- `受注番号未採番`
- `設計リスト作成中`
- `手配前処理`
- `購買手配中`
- `手配完了`

## 添付スロット
- 1: 注文情報（OCR/受注情報抽出対象）
- 2: 設計リスト
- 3: 添付書類
- 4: 緊急作業指示書
- 5: 図面
- 6: APからの資料

## 技術スタック
- Backend: FastAPI
- Frontend: HTML / JavaScript / CSS
- Database: SQLite（ローカル） / PostgreSQL（AWS想定）
- Storage: ローカル `uploads/` / S3
- Queue: SQS（AWS非同期OCR）
- OCR: Tesseract (`pytesseract`)
- PDF: `pdfplumber`, `PyMuPDF`

## クイックスタート（ローカル）

### 1. 仮想環境
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. 依存関係
```bash
pip install -r requirements.txt
```

### 3. Tesseract インストール
- `tesseract` コマンドを PATH に通す
- 日本語OCRを使う場合は `jpn` 言語データを追加

### 4. 起動
```bash
uvicorn app:app --reload
```

- URL: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Docker 構成（アプリ + PostgreSQL）

```bash
docker compose up --build
```

- アプリ: [http://127.0.0.1:18000](http://127.0.0.1:18000)
- DB: PostgreSQL (`localhost:5432`)

## 環境変数

`.env.example` をベースに設定してください。

主要項目:
- `DATABASE_URL`（未指定時は SQLite）
- `STORAGE_BACKEND=local|s3`
- `UPLOAD_DIR`（local 時）
- `S3_BUCKET`, `S3_PREFIX`, `AWS_REGION`（s3 時）
- `OCR_ASYNC_ENABLED=true|false`
- `OCR_QUEUE_BACKEND=sqs`
- `OCR_QUEUE_URL`（SQS URL）
- `S3_PUBLIC_BASE_URL`（CloudFront 等を使う場合、任意）

## AWS 展開

推奨構成:
- ECS Fargate（FastAPI + OCR worker）
- RDS PostgreSQL
- S3（添付保存）
- SQS（OCRジョブ）
- ALB + ACM + Route53

手順詳細は [docs/aws-deployment.md](docs/aws-deployment.md) を参照してください。
Terraform 雛形は [infra/terraform/README.md](infra/terraform/README.md) を参照してください。
権限確認は [scripts/aws-preflight.sh](/Users/matsumototakahiro/order-automation-poc/scripts/aws-preflight.sh) を使えます。

### オンデマンド起動（コスト最適化）
- `infra/terraform/terraform.tfvars` は `desired_count=0`, `worker_desired_count=0` を既定にしています。
- 必要時だけ起動/停止:
```bash
AWS_PROFILE=terraform-deployer AWS_REGION=ap-northeast-1 ./scripts/aws-scale-services.sh up
AWS_PROFILE=terraform-deployer AWS_REGION=ap-northeast-1 ./scripts/aws-scale-services.sh status
AWS_PROFILE=terraform-deployer AWS_REGION=ap-northeast-1 ./scripts/aws-scale-services.sh down
```

## 主要 API
- `POST /cards`
- `POST /cards/update`
- `POST /upload`
- `POST /ocr`
- `POST /parse`
- `GET /kanban`
- `POST /update-status`
- `POST /approve-order`
- `POST /generate-order-candidates`
- `GET /documents/{document_id}`
- `GET /automation-logs`
- `GET /export-csv`

## 補足
- `poc.db` と `uploads/` は `.gitignore` 済みです。
- 現在は PoC で、認証・権限制御は未実装です。

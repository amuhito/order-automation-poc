# order-automation-poc

製造業向けの受注・手配ボード POC です。  
Trello 風のカンバン UI 上でカードを管理し、カード単位でファイルを添付しながら `受注番号 / 機械番号 / 型式 / 客先名 / 希望所要日数` を扱えます。

## Features

- カンバン管理
  - `受注番号未採番`
  - `設計リスト作成中`
  - `手配前処理`
  - `購買手配中`
  - `手配完了`
- `受注番号未採番` 列でカード追加
- カードのドラッグ＆ドロップ移動
- カード詳細で基本情報を編集
- カードごとの添付ファイル管理
  - 添付ファイル1: 注文情報
  - 添付ファイル2: 設計リスト
  - 添付ファイル3: 添付書類
  - 添付ファイル4: 緊急作業指示書
  - 添付ファイル5: 図面
  - 添付ファイル6: APからの資料
- 注文情報ファイルの OCR と基本情報抽出
- CSV 出力

## Tech Stack

- Backend: FastAPI
- Frontend: HTML / JavaScript
- Database: SQLite
- OCR: Tesseract + pytesseract
- PDF: pdfplumber / PyMuPDF

## Project Structure

```text
order-automation-poc/
├─ app.py
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ src/
│  ├─ automation_service.py
│  ├─ db.py
│  ├─ ocr_service.py
│  ├─ order_parser.py
│  └─ parser.py
└─ static/
   ├─ index.html
   ├─ app.js
   └─ styles.css
```

## Setup

### 1. Create venv

```powershell
python -m venv .venv
```

### 2. Activate venv

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Install Tesseract OCR

- `tesseract` コマンドが PATH から呼べるようにしてください
- 日本語を読む場合は `jpn` 言語データも入れてください

### 5. Start app

```powershell
uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Main APIs

- `POST /cards`
- `POST /cards/update`
- `POST /upload`
- `POST /ocr`
- `POST /parse`
- `GET /kanban`
- `POST /update-status`
- `POST /approve-order`
- `GET /documents/{document_id}`
- `GET /export-csv`

## Card Data Model

- `order_number`
- `machine_number`
- `model`
- `customer_name`
- `requested_lead_days`
- `attachments_json`
- `ocr_text`
- `ocr_meta`
- `status`

## Notes

- 添付ファイル1に注文情報をアップロードすると、OCR と簡易パーサーで基本項目を補完します
- `poc.db` と `uploads/` は Git 管理対象外です
- この POC は最小構成を優先しているため、入力ルールや OCR 抽出ロジックは今後拡張前提です

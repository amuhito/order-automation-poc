# order-automation-poc

Manufacturing order board POC built with FastAPI, SQLite, OCR, and a Trello-like kanban UI.

## Overview

This project is a lightweight proof of concept for managing manufacturing order work on cards.

Each card can store:

- Order number
- Machine number
- Model
- Customer name
- Requested lead days
- Multiple attachment slots

The UI supports:

- Kanban columns for workflow status
- Creating cards in the backlog column
- Drag and drop between status columns
- Editing card details
- Uploading files inside each card
- OCR extraction from the order-information attachment

## Status Groups

- `受注番号未採番`
- `設計リスト作成中`
- `手配前処理`
- `購買手配中`
- `手配完了`

## Attachment Slots

- Attachment 1: 注文情報
- Attachment 2: 設計リスト
- Attachment 3: 添付書類
- Attachment 4: 緊急作業指示書
- Attachment 5: 図面
- Attachment 6: APからの資料

## Tech Stack

- Backend: FastAPI
- Frontend: HTML / JavaScript
- Database: SQLite
- OCR: Tesseract via `pytesseract`
- PDF processing: `pdfplumber`, `PyMuPDF`

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

### 1. Create virtual environment

```powershell
python -m venv .venv
```

### 2. Activate virtual environment

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Install Tesseract

Install Tesseract OCR and make sure `tesseract` is available from PATH.

If you need Japanese OCR, also install the `jpn` language data.

### 5. Run the app

```powershell
uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Main API Endpoints

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

## Notes

- Uploading Attachment 1 can populate card fields through OCR parsing.
- `poc.db` and `uploads/` are excluded from Git.
- This project is intentionally minimal and designed to be extended later.

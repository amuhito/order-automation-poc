# 製造業向け発注自動化 POC

紙・PDF・図面ファイルをアップロードし、OCR とルールベース解析で発注候補を作成する最小構成の POC です。

## ディレクトリ構成

```text
order-automation-poc/
├─ app.py
├─ requirements.txt
├─ README.md
├─ poc.db                  # 初回起動後に生成
├─ uploads/                # アップロードファイル保存先
├─ src/
│  ├─ db.py
│  ├─ ocr_service.py
│  └─ parser_service.py
└─ static/
   ├─ index.html
   ├─ app.js
   └─ styles.css
```

## 起動手順

### 1. 仮想環境作成

```bash
python -m venv .venv
```

### 2. 仮想環境有効化

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. ライブラリ導入

```bash
pip install -r requirements.txt
```

### 4. Tesseract OCR をインストール

- Windows: Tesseract 本体をインストールし、`tesseract` コマンドが PATH に通る状態にする
- 日本語 OCR を使う場合は `jpn` 言語データも追加する

### 5. サーバ起動

```bash
uvicorn app:app --reload
```

### 6. ブラウザで開く

```text
http://127.0.0.1:8000
```

## 主な API

- `POST /upload`
- `POST /ocr`
- `POST /parse`
- `GET /kanban`
- `POST /update-status`
- `GET /export-csv`

## 補足

- PDF はまず埋め込みテキスト抽出を試し、文字が無いページだけ OCR します
- 構造化はルールベースのため、帳票フォーマットに合わせて `src/parser_service.py` の正規表現を拡張できます
- CSV 出力は `発注候補` 以外も含めた全件を対象にしています

import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "poc.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL,
            order_number TEXT,
            machine_number TEXT,
            model TEXT,
            customer_name TEXT,
            requested_lead_days TEXT,
            ocr_text TEXT,
            ocr_meta TEXT,
            parsed_json TEXT,
            attachments_json TEXT,
            part_number TEXT,
            quantity INTEGER,
            material TEXT,
            surface TEXT,
            confidence REAL,
            supplier_name TEXT,
            supplier_candidate TEXT,
            order_due_date TEXT,
            automation_decision TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """
    )
    ensure_column(cur, "documents", "part_number", "TEXT")
    ensure_column(cur, "documents", "order_number", "TEXT")
    ensure_column(cur, "documents", "machine_number", "TEXT")
    ensure_column(cur, "documents", "model", "TEXT")
    ensure_column(cur, "documents", "customer_name", "TEXT")
    ensure_column(cur, "documents", "requested_lead_days", "TEXT")
    ensure_column(cur, "documents", "attachments_json", "TEXT")
    ensure_column(cur, "documents", "quantity", "INTEGER")
    ensure_column(cur, "documents", "material", "TEXT")
    ensure_column(cur, "documents", "surface", "TEXT")
    ensure_column(cur, "documents", "confidence", "REAL")
    ensure_column(cur, "documents", "supplier_name", "TEXT")
    ensure_column(cur, "documents", "supplier_candidate", "TEXT")
    ensure_column(cur, "documents", "order_due_date", "TEXT")
    ensure_column(cur, "documents", "automation_decision", "TEXT")
    conn.commit()
    conn.close()


def create_document(filename: str, original_filename: str, file_path: str, status: str, **extra_fields: Any) -> int:
    conn = get_connection()
    cur = conn.cursor()
    fields = {
        "filename": filename,
        "original_filename": original_filename,
        "file_path": file_path,
        "status": status,
        **extra_fields,
    }
    columns = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    cur.execute(
        f"INSERT INTO documents ({columns}) VALUES ({placeholders})",
        list(fields.values()),
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return int(last_id)


def get_all_documents() -> list[dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents ORDER BY id DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_document_by_id(document_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_document_fields(document_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return

    fields = ", ".join(f"{key} = ?" for key in kwargs.keys())
    values = list(kwargs.values()) + [document_id]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE documents SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_history_records(limit: int = 200) -> list[dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, part_number, quantity, material, surface, supplier_name, supplier_candidate, order_due_date, created_at
        FROM documents
        WHERE part_number IS NOT NULL AND part_number != ''
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def ensure_column(cur: sqlite3.Cursor, table_name: str, column_name: str, column_type: str) -> None:
    cur.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cur.fetchall()}
    if column_name not in existing_columns:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def add_automation_log(document_id: int, action: str, message: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO automation_logs (document_id, action, message)
        VALUES (?, ?, ?)
        """,
        (document_id, action, message),
    )
    conn.commit()
    conn.close()


def get_automation_logs(limit: int = 100) -> list[dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT automation_logs.*, documents.original_filename, documents.part_number
        FROM automation_logs
        JOIN documents ON documents.id = automation_logs.document_id
        ORDER BY automation_logs.created_at DESC, automation_logs.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

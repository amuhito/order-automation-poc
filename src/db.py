from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    desc,
    inspect,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = BASE_DIR / "poc.db"


def _normalize_database_url(raw: str | None) -> str:
    if not raw:
        return f"sqlite:///{DEFAULT_SQLITE_PATH}"
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+" not in raw.split("://", 1)[0]:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


def _create_engine() -> Engine:
    database_url = _normalize_database_url(os.getenv("DATABASE_URL"))
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = _create_engine()
metadata = MetaData()


documents = Table(
    "documents",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("filename", String, nullable=False),
    Column("original_filename", String, nullable=False),
    Column("file_path", String, nullable=False),
    Column("status", String, nullable=False),
    Column("order_number", String),
    Column("machine_number", String),
    Column("model", String),
    Column("customer_name", String),
    Column("requested_lead_days", String),
    Column("ocr_text", Text),
    Column("ocr_meta", Text),
    Column("parsed_json", Text),
    Column("attachments_json", Text),
    Column("part_number", String),
    Column("quantity", Integer),
    Column("material", String),
    Column("surface", String),
    Column("confidence", Float),
    Column("supplier_name", String),
    Column("supplier_candidate", String),
    Column("order_due_date", String),
    Column("automation_decision", String),
    Column("ocr_status", String),
    Column("ocr_error", Text),
    Column("ocr_job_id", String),
    Column("ocr_requested_at", DateTime(timezone=False)),
    Column("ocr_started_at", DateTime(timezone=False)),
    Column("ocr_completed_at", DateTime(timezone=False)),
    Column("created_at", DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP")),
)

automation_logs = Table(
    "automation_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("document_id", Integer, ForeignKey("documents.id"), nullable=False),
    Column("action", String, nullable=False),
    Column("message", Text, nullable=False),
    Column("created_at", DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP")),
)


DOCUMENT_COLUMN_TYPES: dict[str, str] = {
    "part_number": "TEXT",
    "order_number": "TEXT",
    "machine_number": "TEXT",
    "model": "TEXT",
    "customer_name": "TEXT",
    "requested_lead_days": "TEXT",
    "attachments_json": "TEXT",
    "quantity": "INTEGER",
    "material": "TEXT",
    "surface": "TEXT",
    "confidence": "REAL",
    "supplier_name": "TEXT",
    "supplier_candidate": "TEXT",
    "order_due_date": "TEXT",
    "automation_decision": "TEXT",
    "ocr_status": "TEXT",
    "ocr_error": "TEXT",
    "ocr_job_id": "TEXT",
    "ocr_requested_at": "TIMESTAMP",
    "ocr_started_at": "TIMESTAMP",
    "ocr_completed_at": "TIMESTAMP",
}


def init_db() -> None:
    metadata.create_all(engine)
    _ensure_document_columns()


def _ensure_document_columns() -> None:
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("documents")}
    missing = [(name, col_type) for name, col_type in DOCUMENT_COLUMN_TYPES.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as conn:
        for column_name, column_type in missing:
            conn.execute(text(f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}"))


def create_document(filename: str, original_filename: str, file_path: str, status: str, **extra_fields: Any) -> int:
    payload = {
        "filename": filename,
        "original_filename": original_filename,
        "file_path": file_path,
        "status": status,
        **extra_fields,
    }
    with engine.begin() as conn:
        result = conn.execute(insert(documents).values(**payload))
        return int(result.inserted_primary_key[0])


def get_all_documents() -> list[dict[str, Any]]:
    stmt = select(documents).order_by(desc(documents.c.id))
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(stmt).mappings().all()]


def get_document_by_id(document_id: int) -> dict[str, Any] | None:
    stmt = select(documents).where(documents.c.id == document_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None


def update_document_fields(document_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    stmt = update(documents).where(documents.c.id == document_id).values(**kwargs)
    with engine.begin() as conn:
        conn.execute(stmt)


def get_history_records(limit: int = 200) -> list[dict[str, Any]]:
    stmt = (
        select(
            documents.c.id,
            documents.c.part_number,
            documents.c.quantity,
            documents.c.material,
            documents.c.surface,
            documents.c.supplier_name,
            documents.c.supplier_candidate,
            documents.c.order_due_date,
            documents.c.created_at,
        )
        .where(documents.c.part_number.is_not(None), documents.c.part_number != "")
        .order_by(desc(documents.c.created_at))
        .limit(limit)
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(stmt).mappings().all()]


def add_automation_log(document_id: int, action: str, message: str) -> None:
    stmt = insert(automation_logs).values(
        document_id=document_id,
        action=action,
        message=message,
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def get_automation_logs(limit: int = 100) -> list[dict[str, Any]]:
    stmt = (
        select(
            automation_logs.c.id,
            automation_logs.c.document_id,
            automation_logs.c.action,
            automation_logs.c.message,
            automation_logs.c.created_at,
            documents.c.original_filename,
            documents.c.part_number,
        )
        .select_from(automation_logs.join(documents, documents.c.id == automation_logs.c.document_id))
        .order_by(desc(automation_logs.c.created_at), desc(automation_logs.c.id))
        .limit(limit)
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(stmt).mappings().all()]

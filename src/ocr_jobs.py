from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.automation_service import evaluate_order_candidate
from src.db import get_document_by_id, get_history_records, update_document_fields
from src.ocr_service import extract_text_from_file
from src.order_parser import parse_order_sheet
from src.parser import parse_procurement_fields
from src.statuses import STATUS_WAITING
from src.storage import as_local_path


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mark_ocr_queued(document_id: int, job_id: str | None = None, status: str = "queued") -> None:
    update_document_fields(
        document_id,
        ocr_status=status,
        ocr_error=None,
        ocr_job_id=job_id,
        ocr_requested_at=utcnow_iso(),
    )


def run_ocr_and_parse_for_document(document_id: int, run_parse: bool = True) -> dict[str, Any]:
    document = get_document_by_id(document_id)
    if not document:
        raise ValueError(f"Document not found: {document_id}")
    if not document.get("file_path"):
        raise ValueError(f"Document has no file path: {document_id}")

    update_document_fields(
        document_id,
        ocr_status="processing",
        ocr_started_at=utcnow_iso(),
        ocr_error=None,
    )

    with as_local_path(str(document["file_path"])) as local_path:
        extracted = extract_text_from_file(local_path)

    parsed_order = parse_order_sheet(extracted["text"])
    updates: dict[str, Any] = {
        "ocr_text": extracted["text"],
        "ocr_meta": json.dumps(extracted["meta"], ensure_ascii=False),
        "order_number": parsed_order.get("order_number") or document.get("order_number"),
        "machine_number": parsed_order.get("machine_number") or document.get("machine_number"),
        "model": parsed_order.get("model") or document.get("model"),
        "customer_name": parsed_order.get("customer_name") or document.get("customer_name"),
        "requested_lead_days": parsed_order.get("requested_lead_days") or document.get("requested_lead_days"),
        "ocr_status": "succeeded",
        "ocr_error": None,
        "ocr_completed_at": utcnow_iso(),
    }
    if updates.get("order_number"):
        updates["original_filename"] = updates["order_number"]

    if run_parse:
        history_records = get_history_records()
        parsed = parse_procurement_fields(extracted["text"], history_records=history_records)
        automation = evaluate_order_candidate({**document, **parsed, "ocr_text": extracted["text"]}, history_records)
        updates.update(
            {
                "parsed_json": json.dumps(parsed, ensure_ascii=False),
                "part_number": parsed.get("part_number"),
                "quantity": parsed.get("quantity"),
                "material": parsed.get("material"),
                "surface": parsed.get("surface"),
                "confidence": parsed.get("confidence"),
                "supplier_candidate": automation.get("supplier_name") or parsed.get("supplier_candidate"),
                "order_due_date": automation.get("order_due_date"),
                "automation_decision": automation.get("review_priority"),
                "status": STATUS_WAITING,
            }
        )

    update_document_fields(document_id, **updates)
    return updates


def mark_ocr_failed(document_id: int, error_message: str) -> None:
    update_document_fields(
        document_id,
        ocr_status="failed",
        ocr_error=error_message[:1000],
        ocr_completed_at=utcnow_iso(),
    )

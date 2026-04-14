from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any


def evaluate_order_candidate(document: dict[str, Any], history_records: list[dict[str, Any]]) -> dict[str, Any]:
    confidence = float(document.get("confidence") or 0)
    part_number = document.get("part_number")
    matched_records = [
        row for row in history_records
        if row.get("part_number") and row.get("part_number") == part_number and row.get("id") != document.get("id")
    ]
    has_past_record = len(matched_records) > 0
    supplier = document.get("supplier_candidate") or document.get("supplier_name") or pick_recent_supplier(matched_records)
    due_date = document.get("order_due_date") or pick_recent_due_date(matched_records) or extract_due_date(document.get("ocr_text") or "")

    is_order_candidate = confidence > 0.8 and has_past_record
    priority = "high_confidence" if confidence > 0.9 and has_past_record else "manual_review"

    return {
        "is_order_candidate": is_order_candidate,
        "review_priority": priority,
        "has_past_record": has_past_record,
        "history_count": len(matched_records),
        "supplier_name": supplier,
        "order_due_date": due_date,
    }


def pick_recent_supplier(records: list[dict[str, Any]]) -> str | None:
    for record in records:
        supplier = record.get("supplier_name") or record.get("supplier_candidate")
        if supplier:
            return str(supplier)
    return None


def pick_recent_due_date(records: list[dict[str, Any]]) -> str | None:
    for record in records:
        if record.get("order_due_date"):
            return str(record["order_due_date"])
    return None


def extract_due_date(text: str) -> str:
    patterns = [
        r"(?:納期|希望納期|Delivery)\s*[:：]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
        r"(?:納期|希望納期|Delivery)\s*[:：]?\s*(\d{1,2}[/-]\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        if len(value.split("/")[0]) == 4 or len(value.split("-")[0]) == 4:
            return value.replace("/", "-")

        current_year = date.today().year
        parts = re.split(r"[/-]", value)
        if len(parts) == 2:
            return f"{current_year:04d}-{int(parts[0]):02d}-{int(parts[1]):02d}"

    return (date.today() + timedelta(days=14)).isoformat()

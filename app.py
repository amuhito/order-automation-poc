import csv
import io
import json
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.automation_service import evaluate_order_candidate
from src.db import (
    add_automation_log,
    create_document,
    get_all_documents,
    get_automation_logs,
    get_document_by_id,
    get_history_records,
    init_db,
    update_document_fields,
)
from src.job_queue import enqueue_ocr_job, is_async_ocr_enabled
from src.ocr_jobs import mark_ocr_failed, mark_ocr_queued, run_ocr_and_parse_for_document
from src.statuses import STATUS_APPROVED, STATUS_CANDIDATE, STATUS_COMPLETED, STATUS_OCR_DONE, STATUS_WAITING
from src.storage import (
    LOCAL_UPLOAD_DIR,
    ensure_storage_ready,
    is_local_storage,
    resolve_file_url,
    upload_file as store_upload_file,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

ensure_storage_ready()
init_db()

app = FastAPI(title="Manufacturing Order Automation POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if is_local_storage():
    app.mount("/files", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="files")


@app.get("/", response_class=HTMLResponse)
def read_index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    document_id: Optional[int] = Form(default=None),
    attachment_slot: Optional[int] = Form(default=None),
) -> dict:
    original_name = Path(file.filename or "uploaded_file").name
    target_name = f"{Path(original_name).stem}_{uuid4().hex[:8]}{Path(original_name).suffix.lower()}"
    stored = store_upload_file(file, target_name)
    target_path = stored["file_path"]
    file_url = stored["file_url"]

    if document_id is not None:
        document = get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        attachments = parse_json_text(document.get("attachments_json"))

        attachment_payload = {
            "filename": target_name,
            "original_filename": original_name,
            "file_path": target_path,
            "file_url": file_url,
        }

        if attachment_slot is not None:
            attachments[str(attachment_slot)] = attachment_payload

        updates = {
            "attachments_json": json.dumps(attachments, ensure_ascii=False),
        }

        # Keep the document's primary file aligned with attachment 1.
        # Other attachment slots should not replace the main preview or OCR target.
        if attachment_slot in {None, 1}:
            updates["filename"] = target_name
            updates["file_path"] = str(target_path)

        if attachment_slot == 1:
            updates["ocr_status"] = "queued"
            updates["ocr_error"] = None

        update_document_fields(
            document_id,
            **updates,
        )

        if attachment_slot == 1:
            if is_async_ocr_enabled():
                job_id = enqueue_ocr_job(document_id, run_parse=True, source="upload_attachment_1")
                mark_ocr_queued(document_id, job_id=job_id, status="queued")
            else:
                try:
                    run_ocr_and_parse_for_document(document_id, run_parse=True)
                except Exception as exc:
                    mark_ocr_failed(document_id, str(exc))

        return {
            "message": "File uploaded successfully",
            "document_id": document_id,
            "filename": target_name,
            "file_url": file_url,
            "attachment_slot": attachment_slot,
        }

    created_id = create_document(
        filename=target_name,
        original_filename=original_name,
        file_path=target_path,
        attachments_json=json.dumps(
            {
                "1": {
                    "filename": target_name,
                    "original_filename": original_name,
                    "file_path": target_path,
                    "file_url": file_url,
                }
            },
            ensure_ascii=False,
        ),
        status=STATUS_WAITING,
        ocr_status="idle",
    )

    return {
        "message": "File uploaded successfully",
        "document_id": created_id,
        "filename": target_name,
        "file_url": file_url,
    }


@app.post("/cards")
async def create_card(title: str = Form(...)) -> dict:
    card_title = title.strip()
    if not card_title:
        raise HTTPException(status_code=400, detail="Title is required")

    document_id = create_document(
        filename="",
        original_filename=card_title,
        file_path="",
        order_number=card_title,
        status=STATUS_OCR_DONE,
        ocr_status="idle",
    )

    add_automation_log(document_id, "card_created", "Card created manually in backlog")

    return {
        "document_id": document_id,
        "title": card_title,
        "status": STATUS_OCR_DONE,
    }


@app.post("/ocr")
async def run_ocr(
    document_id: Optional[int] = Form(default=None),
    filename: Optional[str] = Form(default=None),
) -> dict:
    document = resolve_document(document_id, filename)
    if is_async_ocr_enabled():
        job_id = enqueue_ocr_job(document["id"], run_parse=False, source="manual_ocr")
        mark_ocr_queued(document["id"], job_id=job_id, status="queued")
        return {
            "document_id": document["id"],
            "filename": document["filename"],
            "queued": True,
            "job_id": job_id,
            "status": "queued",
        }

    try:
        updates = run_ocr_and_parse_for_document(document["id"], run_parse=False)
        return {
            "document_id": document["id"],
            "filename": document["filename"],
            "queued": False,
            "status": updates.get("ocr_status"),
        }
    except Exception as exc:
        mark_ocr_failed(document["id"], str(exc))
        raise HTTPException(status_code=500, detail="OCR processing failed") from exc


@app.post("/parse")
async def parse_document(
    document_id: Optional[int] = Form(default=None),
    filename: Optional[str] = Form(default=None),
) -> dict:
    document = resolve_document(document_id, filename)
    if is_async_ocr_enabled():
        job_id = enqueue_ocr_job(document["id"], run_parse=True, source="manual_parse")
        mark_ocr_queued(document["id"], job_id=job_id, status="queued")
        return {
            "document_id": document["id"],
            "filename": document["filename"],
            "queued": True,
            "job_id": job_id,
            "status": "queued",
        }

    try:
        run_ocr_and_parse_for_document(document["id"], run_parse=True)
    except Exception as exc:
        mark_ocr_failed(document["id"], str(exc))
        raise HTTPException(status_code=500, detail="Parse processing failed") from exc

    refreshed = get_document_by_id(document["id"]) or document
    parsed = parse_json_text(refreshed.get("parsed_json"))
    return {
        "document_id": refreshed["id"],
        "filename": refreshed.get("filename"),
        "order_number": refreshed.get("order_number"),
        "machine_number": refreshed.get("machine_number"),
        "model": refreshed.get("model"),
        "customer_name": refreshed.get("customer_name"),
        "requested_lead_days": refreshed.get("requested_lead_days"),
        "part_number": refreshed.get("part_number"),
        "quantity": refreshed.get("quantity"),
        "material": refreshed.get("material"),
        "surface": refreshed.get("surface"),
        "confidence": refreshed.get("confidence"),
        "supplier_candidate": refreshed.get("supplier_candidate"),
        "order_due_date": refreshed.get("order_due_date"),
        "review_priority": refreshed.get("automation_decision"),
        "status": refreshed.get("status"),
        "parsed": parsed,
    }


@app.get("/kanban")
def get_kanban() -> dict:
    documents = get_all_documents()
    columns = [STATUS_OCR_DONE, STATUS_WAITING, STATUS_CANDIDATE, STATUS_APPROVED, STATUS_COMPLETED]
    kanban = {column: [] for column in columns}

    for document in documents:
        status = document["status"] if document["status"] in kanban else STATUS_WAITING
        kanban[status].append(document)

    auto_order_candidates = [
        document
        for document in documents
        if document.get("status") == STATUS_CANDIDATE
        and float(document.get("confidence") or 0) > 0.8
        and bool(document.get("part_number"))
    ]

    return {
        "columns": kanban,
        "items": documents,
        "auto_order_candidates": auto_order_candidates,
        "automation_logs": get_automation_logs(limit=20),
    }


@app.post("/update-status")
async def update_status(
    document_id: int = Form(...),
    status: str = Form(...),
    supplier_name: Optional[str] = Form(default=None),
) -> dict:
    allowed = {STATUS_OCR_DONE, STATUS_WAITING, STATUS_CANDIDATE, STATUS_APPROVED, STATUS_COMPLETED}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")

    document = get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    updates: dict[str, object] = {"status": status}
    if supplier_name is not None:
        updates["supplier_name"] = supplier_name.strip() or None

    update_document_fields(document_id, **updates)

    return {
        "message": "Status updated",
        "document_id": document_id,
        "status": status,
        "supplier_name": updates.get("supplier_name"),
    }


@app.post("/cards/update")
async def update_card_fields(
    document_id: int = Form(...),
    order_number: Optional[str] = Form(default=None),
    machine_number: Optional[str] = Form(default=None),
    model: Optional[str] = Form(default=None),
    customer_name: Optional[str] = Form(default=None),
    requested_lead_days: Optional[str] = Form(default=None),
) -> dict:
    document = get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    updates = {
        "order_number": order_number.strip() if order_number is not None else document.get("order_number"),
        "machine_number": machine_number.strip() if machine_number is not None else document.get("machine_number"),
        "model": model.strip() if model is not None else document.get("model"),
        "customer_name": customer_name.strip() if customer_name is not None else document.get("customer_name"),
        "requested_lead_days": requested_lead_days.strip() if requested_lead_days is not None else document.get("requested_lead_days"),
    }
    if updates["order_number"]:
        updates["original_filename"] = updates["order_number"]

    update_document_fields(document_id, **updates)
    return {"document_id": document_id, "updated": updates}


@app.post("/generate-order-candidates")
async def generate_order_candidates() -> dict:
    history_records = get_history_records()
    documents = get_all_documents()
    results: list[dict] = []

    for document in documents:
        if not document.get("part_number"):
            continue

        automation = evaluate_order_candidate(document, history_records)
        status = STATUS_CANDIDATE if automation["is_order_candidate"] else STATUS_WAITING
        update_document_fields(
            document["id"],
            supplier_candidate=automation.get("supplier_name"),
            order_due_date=automation.get("order_due_date"),
            automation_decision=automation.get("review_priority"),
            status=status,
        )

        if automation["is_order_candidate"]:
            add_automation_log(
                document["id"],
                "candidate_generated",
                "Candidate generated for human review",
            )
            results.append(
                {
                    "document_id": document["id"],
                    "part_number": document.get("part_number"),
                    "supplier_name": automation.get("supplier_name"),
                    "order_due_date": automation.get("order_due_date"),
                    "review_priority": automation.get("review_priority"),
                }
            )
        else:
            update_document_fields(document["id"], status=STATUS_WAITING)

    return {"count": len(results), "items": results}


@app.post("/approve-order")
async def approve_order(
    document_id: int = Form(...),
) -> dict:
    document = get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.get("status") not in {STATUS_CANDIDATE, STATUS_APPROVED}:
        raise HTTPException(status_code=400, detail="Document is not ready for approval")

    next_status = STATUS_APPROVED
    update_document_fields(
        document_id,
        status=next_status,
    )

    add_automation_log(document_id, "order_approved", "Order approved by human reviewer")

    return {
        "document_id": document_id,
        "status": next_status,
    }


@app.get("/automation-logs")
def list_automation_logs() -> dict:
    return {"items": get_automation_logs(limit=100)}


@app.get("/export-csv")
def export_csv() -> StreamingResponse:
    documents = get_all_documents()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "part_number",
            "quantity",
            "supplier_name",
            "order_due_date",
        ]
    )

    for document in documents:
        writer.writerow(
            [
                document.get("part_number", ""),
                document.get("quantity", ""),
                document.get("supplier_candidate") or document.get("supplier_name", ""),
                document.get("order_due_date", ""),
            ]
        )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=order_candidates.csv"},
    )


@app.get("/documents/{document_id}")
def get_document(document_id: int) -> dict:
    document = get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    parsed_json = parse_json_text(document.get("parsed_json"))
    ocr_meta = parse_json_text(document.get("ocr_meta"))
    attachments = hydrate_attachment_urls(parse_json_text(document.get("attachments_json")))
    file_url = resolve_file_url(document.get("file_path") or "", document.get("filename"))

    return {
        **document,
        "parsed": parsed_json,
        "ocr_meta": ocr_meta,
        "attachments": attachments,
        "file_url": file_url,
    }


def resolve_document(document_id: Optional[int], filename: Optional[str]) -> dict:
    document = None
    if document_id is not None:
        document = get_document_by_id(document_id)
    elif filename:
        document = next((row for row in get_all_documents() if row["filename"] == filename), None)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def parse_json_text(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def hydrate_attachment_urls(attachments: dict) -> dict:
    hydrated = {}
    for slot, payload in attachments.items():
        if not isinstance(payload, dict):
            hydrated[slot] = payload
            continue

        item = dict(payload)
        file_path = item.get("file_path")
        filename = item.get("filename")
        if file_path:
            item["file_url"] = resolve_file_url(file_path, filename)
        hydrated[slot] = item
    return hydrated

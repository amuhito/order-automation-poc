import csv
import io
import json
import shutil
from pathlib import Path
from typing import Optional

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
from src.ocr_service import extract_text_from_file
from src.order_parser import parse_order_sheet
from src.parser import parse_procurement_fields


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"

STATUS_OCR_DONE = "\u53d7\u6ce8\u756a\u53f7\u672a\u63a1\u756a"
STATUS_WAITING = "\u8a2d\u8a08\u30ea\u30b9\u30c8\u4f5c\u6210\u4e2d"
STATUS_CANDIDATE = "\u624b\u914d\u524d\u51e6\u7406"
STATUS_APPROVED = "\u8cfc\u8cb7\u624b\u914d\u4e2d"
STATUS_COMPLETED = "\u624b\u914d\u5b8c\u4e86"

UPLOAD_DIR.mkdir(exist_ok=True)
init_db()

app = FastAPI(title="Manufacturing Order Automation POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")


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
    target_name = f"{Path(original_name).stem}_{len(get_all_documents()) + 1}{Path(original_name).suffix}"
    target_path = UPLOAD_DIR / target_name

    with target_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if document_id is not None:
        document = get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        attachments = {}
        if document.get("attachments_json"):
            try:
                attachments = json.loads(document["attachments_json"])
            except json.JSONDecodeError:
                attachments = {}

        if attachment_slot is not None:
            attachments[str(attachment_slot)] = {
                "filename": target_name,
                "original_filename": original_name,
                "file_path": str(target_path),
                "file_url": f"/files/{target_name}",
            }

        updates = {
            "filename": target_name,
            "file_path": str(target_path),
            "attachments_json": json.dumps(attachments, ensure_ascii=False),
        }

        if attachment_slot == 1:
            extracted = extract_text_from_file(str(target_path))
            parsed_order = parse_order_sheet(extracted["text"])
            updates["ocr_text"] = extracted["text"]
            updates["ocr_meta"] = json.dumps(extracted["meta"], ensure_ascii=False)
            updates["order_number"] = parsed_order.get("order_number") or document.get("order_number")
            updates["machine_number"] = parsed_order.get("machine_number") or document.get("machine_number")
            updates["model"] = parsed_order.get("model") or document.get("model")
            updates["customer_name"] = parsed_order.get("customer_name") or document.get("customer_name")
            updates["requested_lead_days"] = parsed_order.get("requested_lead_days") or document.get("requested_lead_days")
            if updates.get("order_number"):
                updates["original_filename"] = updates["order_number"]

        update_document_fields(
            document_id,
            **updates,
        )

        return {
            "message": "File uploaded successfully",
            "document_id": document_id,
            "filename": target_name,
            "file_url": f"/files/{target_name}",
            "attachment_slot": attachment_slot,
        }

    created_id = create_document(
        filename=target_name,
        original_filename=original_name,
        file_path=str(target_path),
        attachments_json=json.dumps(
            {
                "1": {
                    "filename": target_name,
                    "original_filename": original_name,
                    "file_path": str(target_path),
                    "file_url": f"/files/{target_name}",
                }
            },
            ensure_ascii=False,
        ),
        status=STATUS_WAITING,
    )

    return {
        "message": "File uploaded successfully",
        "document_id": created_id,
        "filename": target_name,
        "file_url": f"/files/{target_name}",
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
    extracted = extract_text_from_file(document["file_path"])

    update_document_fields(
        document["id"],
        ocr_text=extracted["text"],
        ocr_meta=json.dumps(extracted["meta"], ensure_ascii=False),
        status=STATUS_OCR_DONE,
    )

    return {
        "document_id": document["id"],
        "filename": document["filename"],
        "text": extracted["text"],
        "meta": extracted["meta"],
    }


@app.post("/parse")
async def parse_document(
    document_id: Optional[int] = Form(default=None),
    filename: Optional[str] = Form(default=None),
) -> dict:
    document = resolve_document(document_id, filename)
    text = document.get("ocr_text") or ""

    if not text.strip():
        extracted = extract_text_from_file(document["file_path"])
        text = extracted["text"]
        update_document_fields(
            document["id"],
            ocr_text=text,
            ocr_meta=json.dumps(extracted["meta"], ensure_ascii=False),
            status=STATUS_OCR_DONE,
        )

    parsed = parse_procurement_fields(text, history_records=get_history_records())
    history_records = get_history_records()
    automation = evaluate_order_candidate({**document, **parsed, "ocr_text": text}, history_records)
    next_status = STATUS_WAITING

    update_document_fields(
        document["id"],
        parsed_json=json.dumps(parsed, ensure_ascii=False),
        part_number=parsed.get("part_number"),
        quantity=parsed.get("quantity"),
        material=parsed.get("material"),
        surface=parsed.get("surface"),
        confidence=parsed.get("confidence"),
        supplier_candidate=automation.get("supplier_name") or parsed.get("supplier_candidate"),
        order_due_date=automation.get("order_due_date"),
        automation_decision=automation.get("review_priority"),
        status=next_status,
    )

    return {
        "document_id": document["id"],
        "filename": document["filename"],
        "order_number": document.get("order_number"),
        "machine_number": document.get("machine_number"),
        "model": document.get("model"),
        "customer_name": document.get("customer_name"),
        "requested_lead_days": document.get("requested_lead_days"),
        "part_number": parsed.get("part_number"),
        "quantity": parsed.get("quantity"),
        "material": parsed.get("material"),
        "surface": parsed.get("surface"),
        "confidence": parsed.get("confidence"),
        "supplier_candidate": automation.get("supplier_name") or parsed.get("supplier_candidate"),
        "matched_history_count": automation.get("history_count"),
        "order_due_date": automation.get("order_due_date"),
        "is_order_candidate": automation.get("is_order_candidate"),
        "review_priority": automation.get("review_priority"),
        "status": next_status,
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

    parsed_json = {}
    if document.get("parsed_json"):
        try:
            parsed_json = json.loads(document["parsed_json"])
        except json.JSONDecodeError:
            parsed_json = {}

    ocr_meta = {}
    if document.get("ocr_meta"):
        try:
            ocr_meta = json.loads(document["ocr_meta"])
        except json.JSONDecodeError:
            ocr_meta = {}

    return {
        **document,
        "parsed": parsed_json,
        "ocr_meta": ocr_meta,
        "attachments": json.loads(document["attachments_json"]) if document.get("attachments_json") else {},
        "file_url": f"/files/{document['filename']}" if document.get("filename") else None,
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

#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db import init_db
from src.job_queue import delete_ocr_job, receive_ocr_jobs
from src.ocr_jobs import mark_ocr_failed, run_ocr_and_parse_for_document
from src.storage import ensure_storage_ready


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ocr-worker")


def parse_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def run_forever() -> None:
    wait_seconds = int(os.getenv("OCR_WORKER_WAIT_SECONDS", "20"))
    idle_sleep = float(os.getenv("OCR_WORKER_IDLE_SLEEP_SECONDS", "1"))
    batch_size = int(os.getenv("OCR_WORKER_BATCH_SIZE", "1"))

    while True:
        messages = receive_ocr_jobs(max_messages=batch_size, wait_seconds=wait_seconds)
        if not messages:
            time.sleep(idle_sleep)
            continue

        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            document_id: int | None = None
            try:
                body = json.loads(message.get("Body") or "{}")
                raw_document_id = body.get("document_id")
                if raw_document_id is None:
                    raise ValueError("document_id is missing in queue message")
                document_id = int(raw_document_id)
                run_parse = parse_bool(body.get("run_parse"), True)
                logger.info("Processing OCR job document_id=%s parse=%s", document_id, run_parse)
                run_ocr_and_parse_for_document(document_id=document_id, run_parse=run_parse)
                delete_ocr_job(receipt_handle)
            except Exception as exc:
                logger.exception("OCR job failed")
                if document_id is not None:
                    mark_ocr_failed(document_id, str(exc))
                delete_ocr_job(receipt_handle)


if __name__ == "__main__":
    ensure_storage_ready()
    init_db()
    run_forever()

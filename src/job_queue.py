from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3


def is_async_ocr_enabled() -> bool:
    return os.getenv("OCR_ASYNC_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def get_queue_backend() -> str:
    return os.getenv("OCR_QUEUE_BACKEND", "sqs").strip().lower()


def get_queue_url() -> str:
    return os.getenv("OCR_QUEUE_URL", "").strip()


def _sqs_client():
    kwargs: dict[str, Any] = {}
    region = os.getenv("AWS_REGION")
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    if region:
        kwargs["region_name"] = region
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("sqs", **kwargs)


def enqueue_ocr_job(document_id: int, run_parse: bool = True, source: str = "manual") -> str | None:
    if get_queue_backend() != "sqs":
        return None

    queue_url = get_queue_url()
    if not queue_url:
        raise RuntimeError("OCR_QUEUE_URL is required when OCR_QUEUE_BACKEND=sqs")

    body = {
        "document_id": document_id,
        "run_parse": run_parse,
        "source": source,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    response = _sqs_client().send_message(QueueUrl=queue_url, MessageBody=json.dumps(body, ensure_ascii=False))
    return response.get("MessageId")


def receive_ocr_jobs(max_messages: int = 1, wait_seconds: int = 20) -> list[dict[str, Any]]:
    if get_queue_backend() != "sqs":
        return []

    queue_url = get_queue_url()
    if not queue_url:
        raise RuntimeError("OCR_QUEUE_URL is required when OCR_QUEUE_BACKEND=sqs")

    response = _sqs_client().receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_seconds,
        VisibilityTimeout=300,
        MessageAttributeNames=["All"],
    )
    return response.get("Messages", [])


def delete_ocr_job(receipt_handle: str) -> None:
    if get_queue_backend() != "sqs":
        return

    queue_url = get_queue_url()
    if not queue_url:
        raise RuntimeError("OCR_QUEUE_URL is required when OCR_QUEUE_BACKEND=sqs")

    _sqs_client().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

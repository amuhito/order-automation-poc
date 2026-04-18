from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import boto3
from fastapi import UploadFile


BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "uploads").strip("/")
S3_PUBLIC_BASE_URL = os.getenv("S3_PUBLIC_BASE_URL", "").rstrip("/")
AWS_REGION = os.getenv("AWS_REGION")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")


def get_storage_backend() -> str:
    return os.getenv("STORAGE_BACKEND", "local").strip().lower()


def is_local_storage() -> bool:
    return get_storage_backend() != "s3"


def ensure_storage_ready() -> None:
    if is_local_storage():
        LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return

    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")


def _s3_client():
    kwargs = {}
    if AWS_REGION:
        kwargs["region_name"] = AWS_REGION
    if AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = AWS_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def _join_s3_key(filename: str) -> str:
    if S3_PREFIX:
        return f"{S3_PREFIX}/{filename}"
    return filename


def upload_file(file: UploadFile, target_name: str) -> dict[str, str]:
    if is_local_storage():
        target_path = LOCAL_UPLOAD_DIR / target_name
        with target_path.open("wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)
        return {
            "file_path": str(target_path),
            "file_url": resolve_file_url(str(target_path), target_name),
        }

    key = _join_s3_key(target_name)
    extra_args = {}
    if file.content_type:
        extra_args["ContentType"] = file.content_type

    client = _s3_client()
    upload_kwargs = {
        "Fileobj": file.file,
        "Bucket": S3_BUCKET,
        "Key": key,
    }
    if extra_args:
        upload_kwargs["ExtraArgs"] = extra_args
    client.upload_fileobj(**upload_kwargs)

    s3_path = f"s3://{S3_BUCKET}/{key}"
    return {
        "file_path": s3_path,
        "file_url": resolve_file_url(s3_path, target_name),
    }


def is_s3_path(path: str) -> bool:
    return str(path).startswith("s3://")


def _split_s3_path(path: str) -> tuple[str, str]:
    parsed = urlparse(path)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 path: {path}")
    return parsed.netloc, parsed.path.lstrip("/")


def resolve_file_url(file_path: str, filename: str | None = None) -> str | None:
    if not file_path:
        return None

    if is_s3_path(file_path):
        bucket, key = _split_s3_path(file_path)
        if S3_PUBLIC_BASE_URL:
            return f"{S3_PUBLIC_BASE_URL}/{key}"

        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=3600,
        )

    local_name = filename or Path(file_path).name
    return f"/files/{local_name}"


@contextmanager
def as_local_path(file_path: str) -> Iterator[str]:
    if is_s3_path(file_path):
        bucket, key = _split_s3_path(file_path)
        suffix = Path(key).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            _s3_client().download_file(bucket, key, str(temp_path))
            yield str(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return

    yield file_path

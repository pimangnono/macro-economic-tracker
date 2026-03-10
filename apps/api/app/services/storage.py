from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any

from app.core.config import get_settings


@dataclass(slots=True)
class StoredArtifact:
    kind: str
    url: str | None = None
    storage_key: str | None = None
    inline_text: str | None = None
    inline_json: dict[str, Any] | None = None
    content_type: str | None = None
    generated: bool = True
    status: str = "ready"

    def to_manifest(self) -> dict[str, Any]:
        return asdict(self)


def _storage_client():
    settings = get_settings()
    if not (
        settings.s3_endpoint
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
        and settings.s3_bucket
    ):
        return None
    try:  # pragma: no cover - boto3 is optional in local dev
        import boto3
    except Exception:
        return None

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )


def _upload_bytes(storage_key: str, payload: bytes, *, content_type: str) -> tuple[str, str] | None:
    client = _storage_client()
    if client is None:
        return None
    settings = get_settings()
    fileobj = BytesIO(payload)
    try:
        client.upload_fileobj(  # pragma: no cover - depends on external service
            fileobj,
            settings.s3_bucket,
            storage_key,
            ExtraArgs={"ContentType": content_type},
        )
    except Exception:
        return None
    base_url = settings.s3_endpoint.rstrip("/")
    return storage_key, f"{base_url}/{settings.s3_bucket}/{storage_key}"


def store_json_artifact(kind: str, payload: dict[str, Any], storage_key: str) -> StoredArtifact:
    encoded = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    uploaded = _upload_bytes(storage_key, encoded, content_type="application/json")
    if uploaded is not None:
        key, url = uploaded
        return StoredArtifact(kind=kind, url=url, storage_key=key, content_type="application/json")
    return StoredArtifact(
        kind=kind,
        inline_json=payload,
        content_type="application/json",
        status="inline_fallback",
    )


def store_text_artifact(kind: str, payload: str, storage_key: str, *, content_type: str) -> StoredArtifact:
    encoded = payload.encode("utf-8")
    uploaded = _upload_bytes(storage_key, encoded, content_type=content_type)
    if uploaded is not None:
        key, url = uploaded
        return StoredArtifact(kind=kind, url=url, storage_key=key, content_type=content_type)
    return StoredArtifact(
        kind=kind,
        inline_text=payload,
        content_type=content_type,
        status="inline_fallback",
    )


def store_binary_artifact(kind: str, payload: bytes, storage_key: str, *, content_type: str) -> StoredArtifact:
    uploaded = _upload_bytes(storage_key, payload, content_type=content_type)
    if uploaded is not None:
        key, url = uploaded
        return StoredArtifact(kind=kind, url=url, storage_key=key, content_type=content_type)
    return StoredArtifact(
        kind=kind,
        inline_text=f"data:{content_type};base64,{base64.b64encode(payload).decode('ascii')}",
        content_type=content_type,
        status="inline_fallback",
    )

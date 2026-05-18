"""Cloudflare R2 access — S3-compatible API.

R2 prefix convention (see plan §7):
  tenant/{tenant_id}/upload/{upload_id}/...
  tenant/{tenant_id}/render/{render_id}/...
  tenant/{tenant_id}/export/{export_id}/{platform}.mp4
"""
from __future__ import annotations

from typing import Any

import boto3
from botocore.client import Config

from api.config import get_settings


def _client() -> Any:
    s = get_settings()
    endpoint = f"https://{s.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4", region_name="auto"),
    )


def upload_key(tenant_id: str, upload_id: str, filename: str) -> str:
    return f"tenant/{tenant_id}/upload/{upload_id}/{filename}"


def render_key(tenant_id: str, render_id: str, filename: str) -> str:
    return f"tenant/{tenant_id}/render/{render_id}/{filename}"


def export_key(tenant_id: str, export_id: str, platform: str) -> str:
    return f"tenant/{tenant_id}/export/{export_id}/{platform}.mp4"


def presign_put(key: str, content_type: str, expires_s: int = 3600) -> str:
    s = get_settings()
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": s.r2_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_s,
    )


def presign_get(key: str, expires_s: int = 3600) -> str:
    s = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.r2_bucket, "Key": key},
        ExpiresIn=expires_s,
    )

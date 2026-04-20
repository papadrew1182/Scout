"""Supabase Storage service.

Uses httpx directly (no SDK) to keep dependencies minimal.
All calls are async-compatible — use within FastAPI async routes.

Environment variables (via Settings with SCOUT_ prefix):
  SCOUT_SUPABASE_URL              — e.g. https://xxx.supabase.co
  SCOUT_SUPABASE_SERVICE_ROLE_KEY — service-role JWT (NEVER hardcode)
  SCOUT_SUPABASE_STORAGE_BUCKET   — defaults to "attachments"
"""

import base64
import uuid
from datetime import datetime

import httpx

from app.config import settings

STORAGE_BASE = f"{settings.supabase_url}/storage/v1"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }


def _ext_from_content_type(ct: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "application/pdf": ".pdf",
    }.get(ct, ".bin")


async def upload_file(
    file_bytes: bytes,
    content_type: str,
    family_id: str,
    member_id: str,
    filename: str | None = None,
) -> dict:
    """Upload a file to Supabase Storage.

    Returns {"path": ..., "signed_url": ..., "content_type": ...}.
    The signed URL has a 1-hour expiry.
    """
    ext = _ext_from_content_type(content_type)
    safe_name = filename or f"{uuid.uuid4().hex[:12]}{ext}"
    date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
    path = f"{family_id}/{member_id}/{date_prefix}/{safe_name}"

    bucket = settings.supabase_storage_bucket
    url = f"{STORAGE_BASE}/object/{bucket}/{path}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            content=file_bytes,
            headers={
                **_headers(),
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )
        resp.raise_for_status()

    signed_url = await create_signed_url(path, expires_in=3600)
    return {"path": path, "signed_url": signed_url, "content_type": content_type}


async def create_signed_url(path: str, expires_in: int = 3600) -> str:
    """Create a time-limited signed URL for a private storage object."""
    bucket = settings.supabase_storage_bucket
    url = f"{STORAGE_BASE}/object/sign/{bucket}/{path}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=_headers(),
            json={"expiresIn": expires_in},
        )
        resp.raise_for_status()
        data = resp.json()

    return f"{settings.supabase_url}/storage/v1{data['signedURL']}"


async def delete_file(path: str) -> None:
    """Delete a file from storage."""
    bucket = settings.supabase_storage_bucket
    url = f"{STORAGE_BASE}/object/{bucket}"

    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            url,
            headers={**_headers(), "Content-Type": "application/json"},
            json={"prefixes": [path]},
        )
        resp.raise_for_status()


async def download_file_base64(path: str) -> tuple[str, str]:
    """Download a file and return (base64_data, content_type).

    Used by the AI chat path to inline attachments as Claude vision
    content blocks — Anthropic's base64 image source format.
    """
    bucket = settings.supabase_storage_bucket
    url = f"{STORAGE_BASE}/object/{bucket}/{path}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()

    b64 = base64.b64encode(resp.content).decode()
    ct = resp.headers.get("content-type", "image/jpeg")
    # Strip charset/boundary suffixes — Anthropic wants bare MIME type
    ct = ct.split(";")[0].strip()
    return b64, ct

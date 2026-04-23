"""Storage routes — file upload + signed-URL resolver.

POST /api/storage/upload
  Accepts a multipart file upload (images + PDF, max 10 MB).
  Stores the file under {family_id}/{member_id}/{date}/{filename} in
  the Supabase Storage bucket configured by SCOUT_SUPABASE_STORAGE_BUCKET.
  Returns {path, signed_url, content_type}.

GET /api/storage/signed-url?path=...
  Resolves a previously-uploaded storage path to a fresh signed URL.
  Required because signed URLs from /upload expire in 1 hour, so any
  long-lived reference (e.g. chore_templates.photo_example_url holding
  the path) must re-sign on read. Path must begin with the actor's
  family_id to prevent cross-tenant reads.

The endpoints are available only when SCOUT_SUPABASE_URL is configured;
they return 501 otherwise so CI environments without Supabase credentials
fail cleanly.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth import Actor, get_current_actor
from app.config import settings
from app.services.storage import create_signed_url, upload_file

logger = logging.getLogger("scout.storage")

router = APIRouter(prefix="/api/storage", tags=["storage"])

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    actor: Actor = Depends(get_current_actor),
):
    """Upload a file to Supabase Storage.

    Returns {path, signed_url, content_type}. The signed URL expires in
    1 hour. For conversation replay the frontend should request a fresh
    URL if the stored one has expired (follow-up: GET /api/storage/signed-url).
    """
    # noqa: public-route — any authenticated family member may upload attachments for AI chat and notes; path is namespaced per family, size/type limits enforced below
    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Storage provider not configured (SCOUT_SUPABASE_URL not set).",
        )

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file.content_type}' not allowed. "
                   f"Accepted: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file upload.",
        )
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large (max {MAX_SIZE // 1024 // 1024} MB).",
        )

    try:
        result = await upload_file(
            file_bytes=contents,
            content_type=file.content_type,
            family_id=str(actor.family_id),
            member_id=str(actor.member_id),
            filename=file.filename or None,
        )
    except Exception as e:
        logger.error(
            "storage_upload_fail actor=%s err=%s",
            actor.member_id, str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage provider failed.",
        )

    logger.info(
        "storage_upload_ok actor=%s path=%s size=%d",
        actor.member_id, result["path"], len(contents),
    )
    return result


@router.get("/signed-url")
async def get_signed_url(
    path: str,
    actor: Actor = Depends(get_current_actor),
):
    """Resolve a stored path to a fresh signed URL.

    Returns {path, signed_url, expires_in}. The URL has a 1-hour
    expiry; callers that render long-lived images should re-fetch
    when the previous URL is near its deadline.

    Access control: path must begin with the actor's family_id.
    Cross-tenant reads are rejected with 403. The path structure is
    {family_id}/{member_id}/{date}/{filename} per upload_file; the
    family_id prefix is the tenancy boundary.
    """
    # noqa: public-route — any authenticated family member may resolve a path within their own family namespace; path-prefix check below is the tenancy gate
    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Storage provider not configured (SCOUT_SUPABASE_URL not set).",
        )

    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing path query parameter.",
        )

    family_prefix = f"{actor.family_id}/"
    if not path.startswith(family_prefix):
        logger.warning(
            "storage_signed_url_forbidden actor=%s path_prefix=%s",
            actor.member_id, path.split("/", 1)[0] if "/" in path else path,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path is outside the actor's family namespace.",
        )

    try:
        signed_url = await create_signed_url(path, expires_in=3600)
    except Exception as e:
        logger.error(
            "storage_signed_url_fail actor=%s err=%s",
            actor.member_id, str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage provider failed.",
        )

    return {"path": path, "signed_url": signed_url, "expires_in": 3600}

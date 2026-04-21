"""Storage routes — file upload endpoint.

POST /api/storage/upload
  Accepts a multipart file upload (images + PDF, max 10 MB).
  Stores the file under {family_id}/{member_id}/{date}/{filename} in
  the Supabase Storage bucket configured by SCOUT_SUPABASE_STORAGE_BUCKET.
  Returns {path, signed_url, content_type}.

The endpoint is available only when SCOUT_SUPABASE_URL is configured;
it returns 501 otherwise so CI environments without Supabase credentials
fail cleanly.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth import Actor, get_current_actor
from app.config import settings
from app.services.storage import upload_file

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

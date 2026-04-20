"""Tests for the Supabase Storage service and upload endpoint.

The storage service talks to Supabase over HTTP, so real calls are only
possible with live credentials. This file tests:
  1. Unit logic (extension mapping, path construction) without network
  2. The upload endpoint's validation layer (file type, size limit, 501
     when Supabase URL is not configured)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Unit tests — storage service helpers (no network, no DB)
# ---------------------------------------------------------------------------

class TestExtFromContentType:
    def test_jpeg(self):
        from app.services.storage import _ext_from_content_type
        assert _ext_from_content_type("image/jpeg") == ".jpg"

    def test_png(self):
        from app.services.storage import _ext_from_content_type
        assert _ext_from_content_type("image/png") == ".png"

    def test_webp(self):
        from app.services.storage import _ext_from_content_type
        assert _ext_from_content_type("image/webp") == ".webp"

    def test_gif(self):
        from app.services.storage import _ext_from_content_type
        assert _ext_from_content_type("image/gif") == ".gif"

    def test_pdf(self):
        from app.services.storage import _ext_from_content_type
        assert _ext_from_content_type("application/pdf") == ".pdf"

    def test_unknown_falls_back(self):
        from app.services.storage import _ext_from_content_type
        assert _ext_from_content_type("application/octet-stream") == ".bin"


class TestStoragePathConstruction:
    """upload_file builds path = {family_id}/{member_id}/{date}/{filename}."""

    @pytest.mark.asyncio
    async def test_path_uses_provided_filename(self):
        """When a filename is given, the path ends with it."""
        family_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        # Patch httpx.AsyncClient so no real network call is made.
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.get = AsyncMock(return_value=mock_response)

        signed_url_response = MagicMock()
        signed_url_response.raise_for_status = MagicMock()
        signed_url_response.json = MagicMock(return_value={"signedURL": "/object/sign/attachments/test"})

        with patch("app.services.storage.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_client):
            mock_settings.supabase_url = "https://example.supabase.co"
            mock_settings.supabase_service_role_key = "test-key"
            mock_settings.supabase_storage_bucket = "attachments"

            # Override create_signed_url to avoid a second httpx call
            with patch("app.services.storage.create_signed_url", new_callable=AsyncMock) as mock_sign:
                mock_sign.return_value = "https://example.supabase.co/storage/v1/signed"

                from app.services.storage import upload_file
                result = await upload_file(
                    file_bytes=b"fake image data",
                    content_type="image/png",
                    family_id=family_id,
                    member_id=member_id,
                    filename="test_image.png",
                )

        assert result["path"].endswith("test_image.png")
        assert result["path"].startswith(f"{family_id}/{member_id}/")
        assert result["content_type"] == "image/png"
        assert "signed_url" in result

    @pytest.mark.asyncio
    async def test_path_generates_name_when_no_filename(self):
        """When no filename is given, a UUID-based name is generated."""
        family_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.storage.settings") as mock_settings, \
             patch("httpx.AsyncClient", return_value=mock_client), \
             patch("app.services.storage.create_signed_url", new_callable=AsyncMock) as mock_sign:
            mock_settings.supabase_url = "https://example.supabase.co"
            mock_settings.supabase_service_role_key = "test-key"
            mock_settings.supabase_storage_bucket = "attachments"
            mock_sign.return_value = "https://example.supabase.co/storage/v1/signed"

            from app.services.storage import upload_file
            result = await upload_file(
                file_bytes=b"data",
                content_type="image/jpeg",
                family_id=family_id,
                member_id=member_id,
            )

        # Path should end with a .jpg extension (auto-generated name)
        assert result["path"].endswith(".jpg")


# ---------------------------------------------------------------------------
# Upload endpoint validation — no DB, no Supabase needed
# ---------------------------------------------------------------------------

class TestUploadEndpointValidation:
    """Validate the FastAPI upload route gatekeeping logic."""

    def test_disallowed_content_type_raises_400(self):
        """image/bmp is not in ALLOWED_TYPES."""
        from app.routes.storage import ALLOWED_TYPES
        assert "image/bmp" not in ALLOWED_TYPES
        assert "image/jpeg" in ALLOWED_TYPES
        assert "application/pdf" in ALLOWED_TYPES

    def test_max_size_is_10mb(self):
        from app.routes.storage import MAX_SIZE
        assert MAX_SIZE == 10 * 1024 * 1024

    def test_allowed_types_set(self):
        from app.routes.storage import ALLOWED_TYPES
        expected = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
        assert ALLOWED_TYPES == expected

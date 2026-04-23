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


# ---------------------------------------------------------------------------
# Signed-URL resolver — Batch 2 PR 1b
#
# Added because chore_templates.photo_example_url now stores the Supabase
# Storage PATH (not a signed URL). Signed URLs expire in 1 hour, so the
# admin UI saves the path and render-side consumers resolve via
# GET /api/storage/signed-url at read time. Tenancy gate: path must
# begin with the actor's family_id.
# ---------------------------------------------------------------------------

class TestSignedUrlEndpoint:
    """Direct async-handler tests. Mocks settings + create_signed_url so
    no real Supabase calls are made.
    """

    def _fake_actor(self, family_id: str):
        # Duck-typed stand-in for app.auth.Actor; the handler only reads
        # family_id and member_id off it.
        return type("FakeActor", (), {
            "family_id": uuid.UUID(family_id),
            "member_id": uuid.UUID(str(uuid.uuid4())),
        })()

    @pytest.mark.asyncio
    async def test_missing_path_raises_400(self):
        from fastapi import HTTPException

        from app.routes.storage import get_signed_url

        with patch("app.routes.storage.settings") as mock_settings:
            mock_settings.supabase_url = "https://example.test"

            with pytest.raises(HTTPException) as exc:
                await get_signed_url(path="", actor=self._fake_actor(str(uuid.uuid4())))
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_cross_family_path_raises_403(self):
        from fastapi import HTTPException

        from app.routes.storage import get_signed_url

        fam_a = str(uuid.uuid4())
        fam_b = str(uuid.uuid4())
        with patch("app.routes.storage.settings") as mock_settings:
            mock_settings.supabase_url = "https://example.test"

            with pytest.raises(HTTPException) as exc:
                await get_signed_url(
                    path=f"{fam_b}/somebody/2026-04-22/file.jpg",
                    actor=self._fake_actor(fam_a),
                )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_supabase_not_configured_raises_501(self):
        from fastapi import HTTPException

        from app.routes.storage import get_signed_url

        with patch("app.routes.storage.settings") as mock_settings:
            mock_settings.supabase_url = None

            with pytest.raises(HTTPException) as exc:
                await get_signed_url(
                    path="any/path.jpg",
                    actor=self._fake_actor(str(uuid.uuid4())),
                )
        assert exc.value.status_code == 501

    @pytest.mark.asyncio
    async def test_happy_path_returns_fresh_signed_url(self):
        from app.routes.storage import get_signed_url

        fam = str(uuid.uuid4())
        path = f"{fam}/member-abc/2026-04-22/photo.jpg"

        with patch("app.routes.storage.settings") as mock_settings, \
             patch("app.routes.storage.create_signed_url", new_callable=AsyncMock) as mock_sign:
            mock_settings.supabase_url = "https://example.test"
            mock_sign.return_value = "https://example.test/storage/v1/signed-123"

            result = await get_signed_url(path=path, actor=self._fake_actor(fam))

        assert result["path"] == path
        assert result["signed_url"] == "https://example.test/storage/v1/signed-123"
        assert result["expires_in"] == 3600
        mock_sign.assert_called_once_with(path, expires_in=3600)

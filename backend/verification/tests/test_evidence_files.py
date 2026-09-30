import hashlib
import struct
import zlib
from io import BytesIO

import pytest
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from audit.models import AuditLog
from verification.models import EvidenceIntegrityStatus, VerificationEvidence
from verification.services import _validate_pdf, create_verification, start_campaign


def _png_chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    + _png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    + _png_chunk(b"IEND", b"")
)


def _jpeg_segment(marker, data):
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(data) + 2) + data


JPEG = (
    b"\xff\xd8"
    + _jpeg_segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    + _jpeg_segment(0xDB, b"\x00" + b"\x01" * 64)
    + _jpeg_segment(0xC0, b"\x08\x00\x01\x00\x01\x01\x01\x11\x00")
    + _jpeg_segment(0xC4, b"\x00" + bytes([1] + [0] * 15) + b"\x00")
    + _jpeg_segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
    + b"\x00\xff\xd9"
)


def _minimal_pdf(eol=b"\n", xref_body=None, offset_adjustment=0):
    parts = [b"%PDF-1.4" + eol]
    offsets = [0]
    for number, body in (
        (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        (2, b"<< /Type /Pages /Kids [] /Count 0 >>"),
    ):
        offsets.append(sum(map(len, parts)))
        parts.append(f"{number} 0 obj".encode() + eol + body + eol + b"endobj" + eol)
    xref_offset = sum(map(len, parts))
    if xref_body is None:
        xref_body = b"0 3" + eol + b"0000000000 65535 f " + eol
        xref_body += b"".join(f"{offset:010d} 00000 n ".encode() + eol for offset in offsets[1:])
    parts.append(b"xref" + eol + xref_body)
    parts.append(
        b"trailer"
        + eol
        + b"<< /Size 3 /Root 1 0 R >>"
        + eol
        + b"startxref"
        + eol
        + str(xref_offset + offset_adjustment).encode()
        + eol
        + b"%%EOF"
        + eol
    )
    return b"".join(parts)


PDF = _minimal_pdf()


@pytest.mark.parametrize("eol", [b"\n", b"\r\n"])
def test_valid_minimal_classic_pdf_xref_accepts_lf_and_crlf(eol):
    payload = _minimal_pdf(eol=eol)
    _validate_pdf(BytesIO(payload), len(payload))


@pytest.mark.parametrize(
    "xref_body",
    [
        b"",  # The previously accepted empty xref section.
        b"0 1\n",  # One declared entry with none present.
        b"0 3\n0000000000 65535 f \n0000000009 00000 n \n",  # Count mismatch.
        b"0 1\nnot-an-xref-entry\n",
        b"0 1\n0000000000 99999 f \n",  # Generation exceeds the PDF limit.
        b"not a subsection header\n",
        b"0 1\n0000000000 65535",  # Truncated entry without line termination.
    ],
)
def test_malformed_classic_pdf_xref_tables_are_rejected(xref_body):
    payload = _minimal_pdf(xref_body=xref_body)
    with pytest.raises(ValueError):
        _validate_pdf(BytesIO(payload), len(payload))


def test_classic_pdf_startxref_must_point_to_actual_xref_token():
    payload = _minimal_pdf(offset_adjustment=1)
    with pytest.raises(ValueError):
        _validate_pdf(BytesIO(payload), len(payload))


def _storage(tmp_path):
    return {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        "assetflow_private": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }


def _verification(manager, asset, campaign_factory):
    campaign = campaign_factory(actor=manager)
    start_campaign(campaign_id=campaign.pk, actor=manager)
    return create_verification(
        actor=manager,
        campaign_id=campaign.pk,
        asset_id=asset.pk,
        observed_asset_tag=asset.asset_tag,
    )


@pytest.mark.django_db
def test_upload_verifies_actual_bytes_and_authorized_content_download(
    manager, asset_factory, campaign_factory, tmp_path
):
    verification = _verification(manager, asset_factory(), campaign_factory)
    client = APIClient()
    client.force_authenticate(manager)
    with override_settings(STORAGES=_storage(tmp_path)):
        response = client.post(
            "/api/v1/verification/evidence/",
            {
                "verification_id": str(verification.pk),
                "evidence_type": "PHOTO",
                "file": SimpleUploadedFile("../unsafe\\tag.png", PNG, content_type="text/html"),
            },
            format="multipart",
        )
        assert response.status_code == 201, response.data
        evidence = VerificationEvidence.objects.get(pk=response.data["id"])
        assert evidence.file_name == "tag.png"
        assert evidence.content_type == "image/png"
        assert evidence.byte_size == len(PNG)
        assert evidence.sha256 == hashlib.sha256(PNG).hexdigest()
        assert evidence.integrity_status == EvidenceIntegrityStatus.VERIFIED
        assert "storage_key" not in response.data
        assert "binary_storage_key" not in response.data
        download = client.get(f"/api/v1/verification/evidence/{evidence.pk}/content/")
        assert download.status_code == 200
        assert download["Content-Disposition"].startswith("attachment;")
        assert download["X-Content-Type-Options"] == "nosniff"
        assert b"".join(download.streaming_content) == PNG
        assert AuditLog.objects.filter(
            entity_id=str(evidence.pk), action="VERIFICATION_EVIDENCE_VERIFIED"
        ).exists()
        assert AuditLog.objects.filter(
            entity_id=str(evidence.pk), action="VERIFICATION_EVIDENCE_DOWNLOADED"
        ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "expected_type", "filename", "request_mime"),
    [
        (PNG, "image/png", "misleading.html", "text/html"),
        (JPEG, "image/jpeg", "photo.png", "application/octet-stream"),
        (PDF, "application/pdf", "scan.jpg", "image/jpeg"),
    ],
)
def test_valid_structures_are_identified_from_bytes_not_filename_or_request_mime(
    manager,
    asset_factory,
    campaign_factory,
    tmp_path,
    payload,
    expected_type,
    filename,
    request_mime,
):
    verification = _verification(manager, asset_factory(), campaign_factory)
    client = APIClient()
    client.force_authenticate(manager)
    with override_settings(STORAGES=_storage(tmp_path)):
        response = client.post(
            "/api/v1/verification/evidence/",
            {
                "verification_id": str(verification.pk),
                "evidence_type": "DOCUMENT",
                "file": SimpleUploadedFile(filename, payload, content_type=request_mime),
            },
            format="multipart",
        )
    assert response.status_code == 201, response.data
    evidence = VerificationEvidence.objects.get(pk=response.data["id"])
    assert evidence.content_type == expected_type
    assert evidence.sha256 == hashlib.sha256(payload).hexdigest()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        b"\x89PNG\r\n\x1a\n<html>arbitrary</html>",
        PNG[:-12],
        PNG[:8] + struct.pack(">I4s", 0xFFFFFFFF, b"IHDR") + PNG[16:],
        b"\xff\xd8arbitrary text",
        JPEG[:-2],
        b"\xff\xd8\xff\xe0\x00\x01\xff\xd9",
        b"%PDF-1.7\n<html>arbitrary</html>",
        PDF[:-8],
    ],
)
def test_signature_prefixed_malformed_or_truncated_files_are_rejected(
    manager, asset_factory, campaign_factory, tmp_path, payload
):
    verification = _verification(manager, asset_factory(), campaign_factory)
    client = APIClient()
    client.force_authenticate(manager)
    with override_settings(STORAGES=_storage(tmp_path)):
        response = client.post(
            "/api/v1/verification/evidence/",
            {
                "verification_id": str(verification.pk),
                "evidence_type": "DOCUMENT",
                "file": SimpleUploadedFile("anything.bin", payload),
            },
            format="multipart",
        )
    assert response.status_code == 400
    assert not VerificationEvidence.objects.filter(integrity_status="VERIFIED").exists()


@pytest.mark.django_db
def test_corrupt_stored_evidence_fails_integrity_and_is_not_served(
    manager, asset_factory, campaign_factory, tmp_path
):
    verification = _verification(manager, asset_factory(), campaign_factory)
    evidence = None
    client = APIClient()
    client.force_authenticate(manager)
    with override_settings(STORAGES=_storage(tmp_path)):
        response = client.post(
            "/api/v1/verification/evidence/",
            {
                "verification_id": str(verification.pk),
                "evidence_type": "PHOTO",
                "file": SimpleUploadedFile("photo.png", PNG),
            },
            format="multipart",
        )
        assert response.status_code == 201
        evidence = VerificationEvidence.objects.get(pk=response.data["id"])
        storage = storages["assetflow_private"]
        storage.delete(evidence.binary_storage_key)
        storage.save(evidence.binary_storage_key, SimpleUploadedFile("photo.png", b"corrupt"))
        result = client.get(f"/api/v1/verification/evidence/{evidence.pk}/content/")
        evidence.refresh_from_db()
        assert result.status_code == 409
        assert evidence.integrity_status == EvidenceIntegrityStatus.CORRUPT


@pytest.mark.django_db
def test_rejects_active_format_and_configured_oversize_upload(
    manager, asset_factory, campaign_factory, tmp_path
):
    verification = _verification(manager, asset_factory(), campaign_factory)
    client = APIClient()
    client.force_authenticate(manager)
    url = "/api/v1/verification/evidence/"
    with override_settings(STORAGES=_storage(tmp_path)):
        unsupported = client.post(
            url,
            {
                "verification_id": str(verification.pk),
                "evidence_type": "DOCUMENT",
                "file": SimpleUploadedFile("active.svg", b"<svg/>"),
            },
            format="multipart",
        )
        assert unsupported.status_code == 400
        with override_settings(EVIDENCE_MAX_UPLOAD_BYTES=5):
            oversized = client.post(
                url,
                {
                    "verification_id": str(verification.pk),
                    "evidence_type": "PHOTO",
                    "file": SimpleUploadedFile("large.png", PNG),
                },
                format="multipart",
            )
        assert oversized.status_code == 400
        assert VerificationEvidence.objects.count() == 0


@pytest.mark.django_db
def test_other_organization_cannot_retrieve_evidence_by_uuid(
    manager, foreign_manager, campaign_factory, tmp_path
):
    foreign_campaign = campaign_factory(actor=foreign_manager)
    start_campaign(campaign_id=foreign_campaign.pk, actor=foreign_manager)
    verification = create_verification(
        actor=foreign_manager,
        campaign_id=foreign_campaign.pk,
        observed_asset_tag="unregistered",
    )
    from verification.services import create_evidence

    evidence = create_evidence(
        actor=foreign_manager,
        verification_id=verification.pk,
        evidence_type="PHOTO",
        external_reference="legacy-ref",
    )
    client = APIClient()
    client.force_authenticate(manager)
    assert client.get(f"/api/v1/verification/evidence/{evidence.pk}/").status_code == 404
    assert client.get(f"/api/v1/verification/evidence/{evidence.pk}/content/").status_code == 404


@pytest.mark.django_db
def test_legacy_metadata_is_unverified_and_immutable(manager, asset_factory, campaign_factory):
    verification = _verification(manager, asset_factory(), campaign_factory)
    from verification.services import create_evidence

    evidence = create_evidence(
        actor=manager,
        verification_id=verification.pk,
        evidence_type="PHOTO",
        storage_key="legacy-reference-only",
    )
    assert evidence.integrity_status == EvidenceIntegrityStatus.LEGACY_UNVERIFIED
    evidence.file_name = "changed.png"
    with pytest.raises(Exception, match="immutable"):
        evidence.save()

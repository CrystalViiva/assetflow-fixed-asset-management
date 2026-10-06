# F12 private verification evidence

## Contract and scope

The production backend supports binary `VerificationEvidence` attached to a `PhysicalVerification`, with an optional exception reference that must belong to the same verification. There is no generic `AssetDocument` model or generic asset upload API. Asset Detail therefore labels generic documents as unsupported; the supported upload control appears only on a verification record. Asset-specific verification history remains available through the existing server-filtered verification tab, without fan-out requests for each observation.

The existing F7 `NOTE` evidence row is metadata only (`METADATA_ONLY`). It is shown separately from binary evidence. Binary evidence uses the actual multipart `POST /api/v1/verification/evidence/` contract with `verification_id`, `evidence_type`, and `file`. The content endpoint is the authenticated UUID route `GET /api/v1/verification/evidence/{id}/content/`.

Public metadata includes evidence UUID, organization and verification/exception references, original filename, detected content type, byte size, SHA256, integrity status, uploader email, and timestamps. The serializer does not return the internal `binary_storage_key`; its legacy `storage_key` input is write-only. The DTO drops unknown storage fields and exposes no storage identity.

## Upload and integrity

Django permits PDF, JPEG, and PNG up to the configured `EVIDENCE_MAX_UPLOAD_BYTES` (20 MiB by default). The browser advertises this setting and file types for convenience; Django rechecks actual bytes and size. MIME is detected from signatures. Structural checks validate PNG chunk order/checksums, JPEG frame/scan structure, and bounded classic-PDF cross-reference/trailer structure. Unsupported PDF xref-stream variants are rejected. This is structural validation, not malware scanning, antivirus, CDR, or a safety certification.

The service creates a server-generated key in the private `assetflow_private` storage, writes the upload, reads it back, and compares byte count and SHA256 before publishing `VERIFIED`. Failures are cleaned up or retained as pending cleanup work according to the backend transaction/storage path. Content retrieval rechecks the stored bytes and only serves `VERIFIED` evidence. The endpoint uses attachment disposition and `X-Content-Type-Options: nosniff`; there is no inline application preview.

## Access and user interface

The backend enforces organization ownership, verification/exception relationship, and department-manager scoping. `ADMIN` and `ASSET_MANAGER` can upload through the existing verification write permission; department managers can read/observe within their department but cannot upload evidence through the evidence endpoint. Django remains the authorization boundary. Content access is authenticated and organization-scoped; a foreign evidence UUID is returned as not found.

The verification screen lists notes and binary evidence separately. Uploads use the centralized authenticated client and browser `FormData`; file bytes remain in the component interaction and are never put in TanStack Query. Automatic mutation retry is disabled. If the response is lost, the client checks pre/post server evidence IDs plus the server filename, byte size, and verified state. One unambiguous new row is treated as committed; otherwise the UI blocks replay and asks the user to recheck history. A same-name/same-size concurrent upload can remain uncertain because the current API does not expose an upload idempotency key.

Downloads use the authenticated API client, session-generation fencing, Blob URLs, a sanitized filename, and immediate URL revocation. The UI only offers downloads for Django `VERIFIED` rows. Metadata queries use the existing user/session-generation verification query family and targeted invalidation. Binary content is never cached.

## Audit and master data

The backend emits the evidence upload-started, verified, failed/cleanup, integrity-failed, and downloaded events where those paths occur. React does not create audit rows. Evidence operations do not update Asset master data. Download audit events include the evidence digest, not bytes or a storage path.

## Validation and smoke

Run the isolated smoke with:

```powershell
python scripts/f1-smoke.py --f12
```

It creates a random disposable PostgreSQL database and temporary private storage root, exercises TypeScript through HTTP and Django, uploads structurally valid PDF/JPEG/PNG with spoofed browser MIME, downloads and compares bytes/hash/size, rejects malformed and unsupported files, checks unauthenticated and foreign-tenant access, and verifies the asset-count/master-data boundary and backend audit rows. Both disposable resources are removed in `finally`; the configured application database is never used.

Backend evidence tests remain the source regression suite for malformed/truncated files, unsupported formats, storage integrity failure, tenant scoping, attachment/nosniff headers, and immutability. The F12 frontend adds DTO, multipart transport, upload UI, and authenticated download coverage.

## Limitations

No generic asset documents, warranty repository, arbitrary historical file store, malware scan, or inline preview is provided. The current evidence endpoint has no client idempotency token, so some concurrent/lost-response uploads can only be reported as uncertain. Browser download uses a Blob and is suitable for the configured current upload limit; chunked streaming is not part of this API.

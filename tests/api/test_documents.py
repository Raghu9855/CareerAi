"""API integration tests for document uploading, text extraction, validation, and security."""

import io

import docx
import pytest
from httpx import AsyncClient

MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
)


def create_sample_docx_bytes(content: str = "Senior Backend Engineer with 8 years of Python experience.") -> bytes:
    """Generate in-memory valid DOCX binary bytes."""
    doc = docx.Document()
    doc.add_paragraph(content)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_valid_txt_document(client: AsyncClient) -> None:
    """Verifies uploading a TXT resume and synchronous text extraction."""
    # 1. Register user
    user = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "txtuser@example.com", "password": "Password123!", "full_name": "TXT User"},
        )
    ).json()
    token = user["tokens"]["access_token"]

    txt_content = b"Skills: Python, FastAPI, Docker, Kubernetes, AWS, Machine Learning."
    files = {"file": ("resume.txt", txt_content, "text/plain")}
    data = {"doc_type": "resume"}

    res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        data=data,
    )
    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["filename"].endswith("resume.txt")
    assert doc_data["status"] == "ready"
    assert "Python, FastAPI" in doc_data["extracted_text"]
    assert doc_data["char_count"] > 0


@pytest.mark.asyncio
async def test_upload_valid_docx_document(client: AsyncClient) -> None:
    """Verifies uploading a DOCX resume and text extraction."""
    user = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "docxuser@example.com", "password": "Password123!", "full_name": "DOCX User"},
        )
    ).json()
    token = user["tokens"]["access_token"]

    docx_bytes = create_sample_docx_bytes("Lead Architect specializing in microservices and scikit-learn ML.")
    files = {
        "file": (
            "my_resume.docx",
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert res.status_code == 201
    doc = res.json()
    assert doc["status"] == "ready"
    assert "Lead Architect" in doc["extracted_text"]


@pytest.mark.asyncio
async def test_upload_valid_pdf_document(client: AsyncClient) -> None:
    """Verifies uploading a valid PDF document."""
    user = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "pdfuser@example.com", "password": "Password123!", "full_name": "PDF User"},
        )
    ).json()
    token = user["tokens"]["access_token"]

    files = {"file": ("formal_resume.pdf", MINIMAL_PDF_BYTES, "application/pdf")}
    res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert res.status_code == 201
    doc = res.json()
    assert doc["status"] == "ready"


@pytest.mark.asyncio
async def test_reject_oversized_document(client: AsyncClient) -> None:
    """Verifies rejection of files exceeding the 10MB limit."""
    user = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "bigfile@example.com", "password": "Password123!", "full_name": "Big File"},
        )
    ).json()
    token = user["tokens"]["access_token"]

    # 11 MB payload
    huge_bytes = b"0" * (11 * 1024 * 1024)
    files = {"file": ("giant.txt", huge_bytes, "text/plain")}

    res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "exceeds maximum allowed size" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_reject_wrong_extension_and_mime(client: AsyncClient) -> None:
    """Verifies rejection of unapproved extensions and MIME types."""
    user = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "malicious@example.com", "password": "Password123!", "full_name": "Attacker"},
        )
    ).json()
    token = user["tokens"]["access_token"]

    # 1. Executable file
    files_exe = {"file": ("script.exe", b"MZ\x90\x00executable_bytes", "application/octet-stream")}
    res_exe = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files_exe,
    )
    assert res_exe.status_code == 422
    assert "Unsupported file extension" in res_exe.json()["error"]["message"]

    # 2. Image MIME type
    files_img = {"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")}
    res_img = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files_img,
    )
    assert res_img.status_code == 422


@pytest.mark.asyncio
async def test_reject_spoofed_magic_bytes(client: AsyncClient) -> None:
    """Verifies rejection when extension claims PDF but bytes are corrupt/spoofed."""
    user = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "spoof@example.com", "password": "Password123!", "full_name": "Spoofer"},
        )
    ).json()
    token = user["tokens"]["access_token"]

    # Named .pdf but bytes are plain text
    spoofed_bytes = b"This is not a PDF file header!"
    files = {"file": ("fake.pdf", spoofed_bytes, "application/pdf")}

    res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert res.status_code == 422
    assert "does not match PDF format signature" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_cross_user_document_isolation(client: AsyncClient) -> None:
    """Verifies that User B cannot download or delete User A's uploaded documents."""
    # 1. User A (Owner)
    alice = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "alice_doc@example.com", "password": "Password123!", "full_name": "Alice Doc"},
        )
    ).json()
    alice_token = alice["tokens"]["access_token"]

    # 2. User B (Attacker)
    bob = (
        await client.post(
            "/api/v1/auth/register",
            json={"email": "bob_doc@example.com", "password": "Password123!", "full_name": "Bob Doc"},
        )
    ).json()
    bob_token = bob["tokens"]["access_token"]

    # 3. Alice uploads document
    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {alice_token}"},
        files={"file": ("confidential_resume.txt", b"Alice Confidential Salary $250k", "text/plain")},
    )
    doc_id = upload_res.json()["id"]

    # 4. Bob attempts to GET Alice's document -> 403 Forbidden
    bob_get = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_get.status_code == 403

    # 5. Bob attempts to DOWNLOAD Alice's document -> 403 Forbidden
    bob_download = await client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_download.status_code == 403

    # 6. Bob attempts to DELETE Alice's document -> 403 Forbidden
    bob_del = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_del.status_code == 403

    # 7. Alice can download her own document
    alice_dl = await client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert alice_dl.status_code == 200
    assert b"Alice Confidential" in alice_dl.content

    # 8. Alice deletes her document
    alice_del = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert alice_del.status_code == 204

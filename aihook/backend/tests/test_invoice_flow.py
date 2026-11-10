"""Hồi quy: upload -> OCR -> automatic acceptance -> analytics -> delete."""
from io import BytesIO

import fitz

from app import main
from app.models import Invoice, InvoiceAnalysis
from app.ocr_service import extract_fields, normalize_text


def upload(client, png):
    response = client.post(
        "/api/invoices/upload", files={"file": ("hoa-don.png", png, "image/png")}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_ocr_preserves_vietnamese_original(ocr_text):
    result = extract_fields(ocr_text)
    assert result["seller_name"] == "Công Ty Cổ Phần Nguyễn Gia"
    assert result["address"] == "Số 3 Đường Lê Lợi, Hà Nội"
    assert result["invoice_number"] == "HĐ-012"
    assert result["tax_code"] == "0123456789"
    assert result["total_amount"] == "1.200.000"
    assert normalize_text("ĐƠN VỊ BÁN") == "don vi ban"


def test_upload_rejects_faked_file_and_keeps_no_record(client):
    api, sessions, uploads, _ = client
    response = api.post(
        "/api/invoices/upload",
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400
    assert api.get("/api/invoices").json() == []
    assert list(uploads.iterdir()) == []


def test_upload_rejects_renamed_jpg(client, sample_png):
    api, _, _, _ = client
    response = api.post(
        "/api/invoices/upload",
        files={"file": ("fake.jpg", sample_png, "image/jpeg")},
    )
    assert response.status_code == 400


def test_upload_rejects_large_and_empty(client):
    api, _, uploads, _ = client
    huge = api.post("/api/invoices/upload", files={
        "file": ("huge.png", b"0" * (main.MAX_FILE_SIZE + 1), "image/png")
    })
    assert huge.status_code == 413
    empty = api.post("/api/invoices/upload", files={
        "file": ("empty.png", b"", "image/png")
    })
    assert empty.status_code == 400
    assert list(uploads.iterdir()) == []


def test_upload_pdf_page_limit(client):
    api, _, _, _ = client
    doc = fitz.open()
    for _ in range(main.MAX_PDF_PAGES + 1):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    response = api.post("/api/invoices/upload", files={
        "file": ("large.pdf", data, "application/pdf")
    })
    assert response.status_code == 400


def test_automatic_flow_and_manual_apis_disabled(client, sample_png, ocr_text):
    api, sessions, uploads, monkeypatch = client
    monkeypatch.setattr(main, "extract_text", lambda path: ocr_text)
    invoice_id = upload(api, sample_png)
    data = api.get(f"/api/invoices/{invoice_id}/analysis").json()
    assert data["verification_status"] == "confirmed"
    assert data["seller_name"] == "Công Ty Cổ Phần Nguyễn Gia"
    assert data["total_amount"] == "1200000.00"
    assert api.get("/api/ai-data/summary").json()["invoice_count"] == 1
    assert api.patch(f"/api/invoices/{invoice_id}/review", json={"total_amount": "1"}).status_code == 410
    assert api.post(f"/api/invoices/{invoice_id}/confirm").status_code == 410
    assert api.post(f"/api/invoices/{invoice_id}/analyze").status_code == 409
    assert api.get(f"/api/invoices/{invoice_id}/analysis").json()["total_amount"] == "1200000.00"
    assert api.delete(f"/api/invoices/{invoice_id}").status_code == 200
    assert list(uploads.iterdir()) == []


def test_missing_fields_excluded_and_retry_succeeds(client, sample_png, ocr_text):
    api, _, _, monkeypatch = client
    monkeypatch.setattr(main, "extract_text", lambda path: "HÓA ĐƠN")
    invoice_id = upload(api, sample_png)
    data = api.get(f"/api/invoices/{invoice_id}/analysis").json()
    assert data["verification_status"] == "needs_review"
    assert data["validation"]["errors"]
    assert api.get("/api/ai-data/summary").json()["invoice_count"] == 0
    monkeypatch.setattr(main, "extract_text", lambda path: ocr_text)
    assert api.post(f"/api/invoices/{invoice_id}/analyze").json()["verification_status"] == "confirmed"


def test_ocr_failure_preserves_uploaded_file(client, sample_png):
    api, _, uploads, monkeypatch = client
    def fail(path):
        raise RuntimeError("OCR unavailable")
    monkeypatch.setattr(main, "extract_text", fail)
    response = api.post("/api/invoices/upload", files={"file": ("test.png", sample_png, "image/png")})
    assert response.status_code == 200
    assert response.json()["processing_error"]
    assert response.json()["status"] == "uploaded"
    assert len(list(uploads.iterdir())) == 1
    assert api.get("/api/ai-data/summary").json()["invoice_count"] == 0


def test_pdf_with_text_layer_is_extracted_without_tesseract(tmp_path, monkeypatch):
    from app.ocr_service import extract_text
    import app.ocr_service as ocr_service

    filename = tmp_path / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Invoice Number: 2026A")
    document.save(filename)
    document.close()

    def do_not_ocr(*args, **kwargs):
        raise AssertionError("PDF có text layer không cần gọi Tesseract")

    monkeypatch.setattr(ocr_service.pytesseract, "image_to_string", do_not_ocr)
    assert "Invoice Number: 2026A" in extract_text(str(filename))


def test_ocr_preserves_combining_unicode_accents():
    import unicodedata
    source = "Đơn vị bán hàng: Công ty Nghệ\n"
    decomposed = unicodedata.normalize("NFD", source)
    assert extract_fields(decomposed)["seller_name"] == unicodedata.normalize(
        "NFD", "Công ty Nghệ"
    )

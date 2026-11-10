from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import fitz
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, inspect, text as sql_text

from app.database import Base, SessionLocal, engine
from app.models import Business, Invoice, InvoiceAnalysis
from app.ocr_service import (
    MAX_IMAGE_PIXELS, MAX_PDF_PAGES, extract_fields, extract_text, normalize_text,
)
from app.routers.ai_data import router as ai_data_router
from app.routers.analytics import router as analytics_router
from app.routers.chat import router as chat_router



# --------------------------------------------------
# Paths and configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


# --------------------------------------------------
# Database initialization & Lifespan
# --------------------------------------------------

def init_database():
    Base.metadata.create_all(bind=engine)
    # Additive migration: existing data remains intact.
    existing = {c['name'] for c in inspect(engine).get_columns('invoices')}
    with engine.begin() as connection:
        for name, kind in [('source_file', 'VARCHAR(1000)'), ('source_page', 'INTEGER')]:
            if name not in existing:
                connection.execute(sql_text(f'ALTER TABLE invoices ADD COLUMN {name} {kind}'))

    with SessionLocal() as db:
        business = db.scalar(
            select(Business).where(Business.id == 1)
        )

        if business is None:
            db.add(
                Business(
                    id=1,
                    name="Doanh nghiệp demo",
                    tax_code=None,
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(title="AIHOOK API", lifespan=lifespan)

# --------------------------------------------------
# Middleware & Routers
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_data_router)
app.include_router(analytics_router)
app.include_router(chat_router)


# --------------------------------------------------
# Helpers (Mục A)
# --------------------------------------------------

def serialize_invoice(invoice: Invoice) -> dict:
    file_path = UPLOAD_DIR / invoice.file_path
    return {
        "source_file": invoice.source_file,
        "source_page": invoice.source_page,
        "id": invoice.id,
        "filename": invoice.file_name,
        "size": file_path.stat().st_size if file_path.is_file() else 0,
        "status": invoice.verification_status,
        "created_at": (
            invoice.created_at.isoformat()
            if invoice.created_at
            else None
        ),
    }



# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "AIHOOK API"}


# --------------------------------------------------
# Upload invoice (Mục B)
# --------------------------------------------------

def validate_upload_content(path: Path, extension: str) -> None:
    """Kiểm tra nội dung thật của file, không tin phần mở rộng / MIME từ client."""
    try:
        if extension == ".pdf":
            with fitz.open(path) as document:
                if not document.is_pdf or document.needs_pass:
                    raise ValueError("PDF không hợp lệ hoặc có mật khẩu.")
                if not 0 < document.page_count <= MAX_PDF_PAGES:
                    raise ValueError(f"PDF phải có từ 1 đến {MAX_PDF_PAGES} trang.")
        else:
            expected = "PNG" if extension == ".png" else "JPEG"
            with Image.open(path) as image:
                if image.format != expected:
                    raise ValueError("Nội dung ảnh không khớp phần mở rộng.")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Ảnh quá lớn để xử lý.")
                image.verify()
    except (ValueError, UnidentifiedImageError, Image.DecompressionBombError, OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Tệp không hợp lệ: {exc}",
        ) from exc


@app.post("/api/invoices/upload")
async def upload_invoice(file: UploadFile = File(...), import_mode: str = Form("single")):
    if import_mode not in {"single", "per_page"}:
        raise HTTPException(400, "Chế độ nhập không hợp lệ.")
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    if not original_name or extension not in ALLOWED_EXTENSIONS:
        await file.close()
        raise HTTPException(
            status_code=400,
            detail="Chỉ chấp nhận file PDF, PNG, JPG hoặc JPEG.",
        )

    invoice_id = str(uuid4())
    stored_filename = f"{invoice_id}{extension}"
    destination = UPLOAD_DIR / stored_filename
    size = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break

                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Dung lượng file vượt quá 10 MB.",
                    )

                output.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="File rỗng, vui lòng chọn file khác.",
            )

        validate_upload_content(destination, extension)

        if import_mode == "per_page" and extension == ".pdf":
            return import_pdf_pages(destination, original_name)

        with SessionLocal() as db:
            business = db.get(Business, 1)
            if business is None:
                raise HTTPException(
                    status_code=500,
                    detail="Không tìm thấy doanh nghiệp mặc định.",
                )

            invoice = Invoice(
                business_id=business.id,
                file_name=original_name,
                file_path=stored_filename,
                verification_status="uploaded",
            )
            db.add(invoice)
            db.commit()
            db.refresh(invoice)

            result = serialize_invoice(invoice)

        # File đã được lưu: lỗi OCR không làm mất file, người dùng có thể thử lại.
        try:
            analysis_result = analyze_invoice(str(result["id"]))
            result["status"] = analysis_result["verification_status"]
        except HTTPException as exc:
            result["processing_error"] = str(exc.detail)
        result["message"] = "Đã lưu tệp; xem trạng thái xử lý OCR."
        return result

    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


# --------------------------------------------------
# List invoices
# --------------------------------------------------

@app.get("/api/invoices")
def list_invoices():
    with SessionLocal() as db:
        statement = select(Invoice).order_by(Invoice.id.desc())
        invoices = db.scalars(statement).all()
        return [serialize_invoice(invoice) for invoice in invoices]


# --------------------------------------------------
# Preview / retrieve invoice file (Mục C)
# --------------------------------------------------

@app.get("/api/invoices/{invoice_id}/file")
def get_invoice_file(invoice_id: str):
    with SessionLocal() as db:
        try:
            numeric_id = int(invoice_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        invoice = db.get(Invoice, numeric_id)
        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        stored_filename = invoice.file_path
        original_filename = invoice.file_name

    file_path = UPLOAD_DIR / stored_filename
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy file trên máy chủ.",
        )

    extension = file_path.suffix.lower()
    
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }

    return FileResponse(
    path=file_path,
    media_type=media_types.get(
        file_path.suffix.lower(),
        "application/octet-stream",
    ),
    filename=invoice.file_name,
    content_disposition_type="inline",
)


def parse_invoice_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(value: str | None) -> Decimal | None:
    """Tiền VND: 1200000 hoặc 1.200.000 hoặc 1,200,000."""
    if not value:
        return None
    value = value.strip().replace(" ", "")
    if not re.fullmatch(r"\d+|\d{1,3}(?:[.,]\d{3})+", value):
        return None
    try:
        return Decimal(value.replace(".", "").replace(",", ""))
    except InvalidOperation:
        return None


def validate_ocr_fields(fields: dict, raw_text: str) -> dict:
    """Kiểm tra dữ liệu trích xuất; không xác thực pháp lý hóa đơn."""
    errors: list[str] = []
    warnings: list[str] = []
    invoice_date = parse_invoice_date(fields.get("invoice_date"))
    total_amount = parse_amount(fields.get("total_amount"))

    normalized_text = normalize_text(raw_text)
    if not any(marker in normalized_text for marker in (
        "hoa don", "invoice", "gia tri gia tang",
    )):
        errors.append("Không nhận diện được dấu hiệu của hóa đơn.")
    if not (fields.get("invoice_number") or "").strip():
        errors.append("Không trích xuất được mã hóa đơn.")
    if invoice_date is None:
        errors.append("Ngày lập hóa đơn thiếu hoặc không hợp lệ.")
    if not (fields.get("seller_name") or "").strip():
        errors.append("Không trích xuất được đơn vị bán.")
    if total_amount is None:
        errors.append("Tổng tiền thiếu hoặc không đúng định dạng.")
    elif total_amount == 0:
        warnings.append("Tổng tiền bằng 0, nên kiểm tra lại.")
    if not fields.get("tax_code"):
        warnings.append("Chưa trích xuất được mã số thuế đơn vị bán.")

    return {"eligible": not errors, "errors": errors, "warnings": warnings}


def serialize_analysis(invoice: Invoice, analysis: InvoiceAnalysis) -> dict:
    """Dữ liệu hiện hành từ Invoice; bản OCR gốc chỉ để đối chiếu."""
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "seller_name": invoice.seller_name,
        "seller_tax_code": invoice.seller_tax_code,
        "total_amount": str(invoice.total_amount) if invoice.total_amount is not None else None,
        "raw_text": analysis.raw_text,
        "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
        "verification_status": invoice.verification_status,
        "validation": validate_ocr_fields(extract_fields(analysis.raw_text), analysis.raw_text),
        "ocr_fields": {
            "invoice_number": analysis.invoice_number,
            "invoice_date": analysis.invoice_date,
            "seller_name": analysis.seller_name,
            "total_amount": analysis.total_amount,
        },
    }


# --------------------------------------------------
# Analyze invoice with OCR (Mục C & D)
# --------------------------------------------------

@app.post("/api/invoices/{invoice_id}/analyze")
def analyze_invoice(invoice_id: str):
    with SessionLocal() as db:
        try:
            numeric_id = int(invoice_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        invoice = db.get(Invoice, numeric_id)
        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        # Không ghi đè dữ liệu đã xác nhận bằng kết quả OCR mới.
        if invoice.verification_status == "confirmed":
            raise HTTPException(
                status_code=409,
                detail="Hóa đơn đã xác nhận. Hãy xem dữ liệu đã lưu thay vì OCR lại.",
            )

        file_path = UPLOAD_DIR / invoice.file_path
        if not file_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy file trên máy chủ.",
            )

        try:
            text = extract_text(str(file_path))
            fields = extract_fields(text)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Không thể phân tích hóa đơn: {exc}",
            ) from exc

        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Không trích xuất được văn bản. Hãy kiểm tra chất lượng ảnh hoặc PDF.",
            )

        analysis_id = str(invoice.id)
        analysis = db.get(InvoiceAnalysis, analysis_id)
        if analysis is None:
            analysis = InvoiceAnalysis(
                invoice_id=analysis_id,
                analyzed_at=datetime.now(timezone.utc),
            )
            db.add(analysis)

        # InvoiceAnalysis chỉ giữ ảnh chụp OCR; không chỉnh sửa khi người dùng review.
        analysis.invoice_number = fields.get("invoice_number")
        analysis.invoice_date = fields.get("invoice_date")
        analysis.seller_name = fields.get("seller_name")
        analysis.total_amount = fields.get("total_amount")
        analysis.raw_text = fields.get("raw_text", "") or ""
        analysis.analyzed_at = datetime.now(timezone.utc)

        invoice.invoice_number = fields.get("invoice_number")
        invoice.invoice_date = parse_invoice_date(fields.get("invoice_date"))
        invoice.seller_name = fields.get("seller_name")
        invoice.seller_tax_code = fields.get("tax_code")
        invoice.total_amount = parse_amount(fields.get("total_amount"))

        validation = validate_ocr_fields(fields, analysis.raw_text)
        # Tự ghi nhận chỉ khi dữ liệu vượt qua kiểm tra.
        invoice.verification_status = "confirmed" if validation["eligible"] else "needs_review"
        db.commit()
        db.refresh(invoice)
        db.refresh(analysis)

        return {
            **serialize_analysis(invoice, analysis),
            "status": "analyzed",
            "validation": validation,
            # Giữ khóa cũ để frontend phiên bản trước không bị hỏng.
            "auto_confirmation": validation,
            "message": "Đã xử lý tự động. Xem trạng thái và kết quả kiểm tra dữ liệu.",
        }



# --------------------------------------------------
# Retrieve saved OCR analysis (Mục C & D)
# --------------------------------------------------



@app.get("/api/invoices/{invoice_id}/analysis")
def get_invoice_analysis(invoice_id: str):
    try:
        numeric_id = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy hóa đơn.",
        )

    with SessionLocal() as db:
        invoice = db.get(Invoice, numeric_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        analysis = db.get(InvoiceAnalysis, str(invoice.id))

        if analysis is None:
            raise HTTPException(
                status_code=404,
                detail="Hóa đơn chưa được phân tích.",
            )

        return serialize_analysis(invoice, analysis)


# --------------------------------------------------
# Delete invoice (Mục C & D)
# --------------------------------------------------

@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str):
    with SessionLocal() as db:
        try:
            numeric_id = int(invoice_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        invoice = db.get(Invoice, numeric_id)
        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        file_path = UPLOAD_DIR / invoice.file_path

        # Xóa kết quả OCR tương ứng nếu có
        analysis = db.get(InvoiceAnalysis, str(invoice.id))
        if analysis:
            db.delete(analysis)

        db.delete(invoice)
        db.commit()

    file_path.unlink(missing_ok=True)

    return {
        "id": invoice.id,
        "message": "Đã xóa hóa đơn.",
    }
    

@app.patch("/api/invoices/{invoice_id}/review")
@app.post("/api/invoices/{invoice_id}/confirm")
def manual_changes_disabled(invoice_id: str):
    raise HTTPException(status_code=410, detail="Đã bỏ chỉnh sửa và xác nhận thủ công. Hệ thống tự ghi nhận sau OCR.")


def import_pdf_pages(source: Path, original_name: str, replace_id: int | None = None):
    """Split only when explicitly selected; each child keeps source and page provenance."""
    paths = []
    try:
        with fitz.open(source) as document:
            for number in range(document.page_count):
                path = UPLOAD_DIR / f"{uuid4()}.pdf"
                with fitz.open() as child:
                    child.insert_pdf(document, from_page=number, to_page=number)
                    child.save(path)
                paths.append(path)
        with SessionLocal() as db:
            if replace_id is not None:
                # Serialize conversion to avoid two requests replacing the same legacy row.
                db.execute(sql_text('BEGIN IMMEDIATE'))
                old = db.get(Invoice, replace_id)
                if old is None or old.source_file:
                    raise HTTPException(409, "Hóa đơn đã được tách hoặc không còn tồn tại.")
                old_analysis = db.get(InvoiceAnalysis, str(replace_id))
                if old_analysis:
                    db.delete(old_analysis)
                db.delete(old)
            invoices = []
            for number, path in enumerate(paths, 1):
                invoice = Invoice(business_id=1, file_name=f"{Path(original_name).stem} · Trang {number}.pdf",
                                  file_path=path.name, source_file=source.name,
                                  source_page=number, verification_status="uploaded")
                db.add(invoice)
                invoices.append(invoice)
            db.commit()
            results = []
            for invoice in invoices:
                db.refresh(invoice)
                results.append(serialize_invoice(invoice))
    except Exception:
        for path in paths:
            path.unlink(missing_ok=True)
        raise
    # OCR failures are isolated per child; uploaded pages remain available for retry.
    for result in results:
        try:
            result['status'] = analyze_invoice(str(result['id']))['verification_status']
        except HTTPException as exc:
            result['processing_error'] = str(exc.detail)
    return {'invoices': results, 'invoice_count': len(results), 'message': 'Đã tách PDF theo từng trang.'}


@app.post('/api/invoices/{invoice_id}/split-pages')
def split_existing_pdf(invoice_id: int):
    with SessionLocal() as db:
        invoice = db.get(Invoice, invoice_id)
        if invoice is None:
            raise HTTPException(404, 'Không tìm thấy hóa đơn.')
        if invoice.source_file:
            raise HTTPException(409, 'Hóa đơn này đã được tách.')
        source = UPLOAD_DIR / invoice.file_path
        original_name = invoice.file_name
        if source.suffix.lower() != '.pdf' or not source.is_file():
            raise HTTPException(400, 'Chỉ tách được PDF còn tồn tại.')
        with fitz.open(source) as document:
            if document.page_count < 2:
                raise HTTPException(400, 'PDF chỉ có một trang, không cần tách.')
    return import_pdf_pages(source, original_name, replace_id=invoice_id)

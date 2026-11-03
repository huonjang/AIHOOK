from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Business, Invoice, InvoiceAnalysis
from app.ocr_service import extract_fields, extract_text
from app.routers.ai_data import router as ai_data_router

from pydantic import BaseModel

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


app = FastAPI(title="AITHOOK API", lifespan=lifespan)

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


# --------------------------------------------------
# Helpers (Mục A)
# --------------------------------------------------

def serialize_invoice(invoice: Invoice) -> dict:
    file_path = UPLOAD_DIR / invoice.file_path
    return {
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
    return {"status": "ok", "service": "AITHOOK API"}


# --------------------------------------------------
# Upload invoice (Mục B)
# --------------------------------------------------

@app.post("/api/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
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
                verification_status="needs_review",
            )
            db.add(invoice)
            db.commit()
            db.refresh(invoice)

            result = serialize_invoice(invoice)

        result["message"] = "Tệp đã được lưu. OCR chưa được thực hiện."
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

    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue

    return None

from decimal import Decimal, InvalidOperation
import re

class InvoiceReviewUpdate(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    seller_name: str | None = None
    seller_tax_code: str | None = None
    total_amount: Decimal | None = None


def parse_invoice_date(value: str | None) -> date | None:
    if not value:
        return None

    value = value.strip()

    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def parse_amount(value: str | None) -> Decimal | None:
    if not value:
        return None

    value = value.strip().replace(" ", "")

    # Chỉ chấp nhận số nguyên hoặc số có dấu phân cách hàng nghìn.
    if not re.fullmatch(r"\d+|\d{1,3}(?:[.,]\d{3})+", value):
        return None

    normalized = value.replace(".", "").replace(",", "")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def validate_invoice_for_auto_confirmation(fields: dict, raw_text: str):
    """
    Kiểm tra tối thiểu trước khi tự xác nhận.
    Không thay thế việc xác minh hóa đơn điện tử với cơ quan thuế.
    """
    errors = []
    warnings = []

    invoice_number = fields.get("invoice_number")
    invoice_date = parse_invoice_date(fields.get("invoice_date"))
    seller_name = fields.get("seller_name")
    total_amount = parse_amount(fields.get("total_amount"))

    # 1. Không chấp nhận tệp không có dấu hiệu nhận diện hóa đơn.
    normalized_text = raw_text.lower()
    invoice_markers = (
        "hoa don",
        "hóa đơn",
        "invoice",
        "gia tri gia tang",
        "giá trị gia tăng",
    )

    if not any(marker in normalized_text for marker in invoice_markers):
        errors.append("Không nhận diện được dấu hiệu của hóa đơn.")

    # 2. Kiểm tra thông tin bắt buộc.
    if not invoice_number or not invoice_number.strip():
        errors.append("Không trích xuất được mã hóa đơn.")

    if invoice_date is None:
        errors.append("Ngày lập hóa đơn thiếu hoặc không hợp lệ.")

    if not seller_name or not seller_name.strip():
        errors.append("Không trích xuất được đơn vị bán.")

    if total_amount is None:
        errors.append("Tổng tiền thiếu hoặc không đúng định dạng.")
    elif total_amount < 0:
        errors.append("Tổng tiền không được âm.")
    elif total_amount == 0:
        warnings.append("Tổng tiền bằng 0, nên kiểm tra lại.")

    # 3. Cảnh báo không đồng nghĩa với lỗi chặn.
    if not fields.get("tax_code"):
        warnings.append("Chưa trích xuất được mã số thuế đơn vị bán.")

    return {
        "eligible": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "parsed_invoice_date": invoice_date,
        "parsed_total_amount": total_amount,
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

        analysis.invoice_number = fields.get("invoice_number")
        analysis.invoice_date = fields.get("invoice_date")
        analysis.seller_name = fields.get("seller_name")
        analysis.total_amount = fields.get("total_amount")
        analysis.raw_text = fields.get("raw_text", "")
        analysis.analyzed_at = datetime.now(timezone.utc)
        
        
# Đồng bộ các trường OCR sang bảng invoices.
        invoice.invoice_number = fields.get("invoice_number")
        invoice.invoice_date = parse_invoice_date(
            fields.get("invoice_date")
        )
        invoice.seller_name = fields.get("seller_name")
        invoice.seller_tax_code = fields.get("tax_code")
        invoice.total_amount = parse_amount(
            fields.get("total_amount")
        )

        
# Kiểm tra kết quả OCR trước khi quyết định trạng thái.
        validation = validate_invoice_for_auto_confirmation(
            fields=fields,
            raw_text=analysis.raw_text,
        )

        if validation["eligible"]:
            invoice.verification_status = "confirmed"
        else:
            invoice.verification_status = "needs_review"

        db.commit()
        db.refresh(analysis)

        return {
            "invoice_id": invoice.id,
            "status": "analyzed",
            "invoice_number": analysis.invoice_number,
            "invoice_date": analysis.invoice_date,
            "seller_name": analysis.seller_name,
            "total_amount": analysis.total_amount,
            "raw_text": analysis.raw_text,
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "verification_status": invoice.verification_status,
            "auto_confirmation": {
                "eligible": validation["eligible"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            },
            "message": (
                "Hóa đơn đã được xác nhận tự động."
                if validation["eligible"]
                else "Hóa đơn cần kiểm tra thêm."
            ),
        }


        return {
            "invoice_id": invoice.id,
            "status": "analyzed",
            "invoice_number": analysis.invoice_number,
            "invoice_date": analysis.invoice_date,
            "seller_name": analysis.seller_name,
            "total_amount": analysis.total_amount,
            "raw_text": analysis.raw_text,
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "message": "Đã trích xuất văn bản thành công.",
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

        return {
            "invoice_id": invoice.id,
            "invoice_number": analysis.invoice_number,
            "invoice_date": analysis.invoice_date,
            "seller_name": analysis.seller_name,
            "total_amount": analysis.total_amount,
            "raw_text": analysis.raw_text,
            "analyzed_at": (
                analysis.analyzed_at.isoformat()
                if analysis.analyzed_at
                else None
            ),
            "verification_status": invoice.verification_status,
        }



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
def review_invoice(
    invoice_id: str,
    payload: InvoiceReviewUpdate,
):
    try:
        numeric_id = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy hóa đơn.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Không có trường dữ liệu nào được gửi để cập nhật.",
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
                status_code=409,
                detail="Hóa đơn chưa được phân tích OCR.",
            )

        for field, value in updates.items():
            setattr(invoice, field, value)

            if field == "invoice_date":
                analysis.invoice_date = (
                    value.isoformat() if value else None
                )
            elif field == "total_amount":
                analysis.total_amount = (
                    str(value) if value is not None else None
                )
            else:
                setattr(analysis, field, value)

        # Mọi chỉnh sửa đều cần được xác nhận lại.
        invoice.verification_status = "needs_review"

        try:
            db.commit()
            db.refresh(invoice)
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Không thể lưu dữ liệu hóa đơn.",
            )

        return {
            "invoice_id": invoice.id,
            "verification_status": invoice.verification_status,
            "message": "Đã cập nhật dữ liệu. Vui lòng xác nhận hóa đơn.",
        }


@app.post("/api/invoices/{invoice_id}/confirm")
def confirm_invoice(invoice_id: str):
    try:
        numeric_id = int(invoice_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy hóa đơn."
        )

    with SessionLocal() as db:
        invoice = db.get(Invoice, numeric_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn."
            )

        # Kiểm tra các trường bắt buộc trước khi xác nhận
        required_fields = {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "seller_name": invoice.seller_name,
            "total_amount": invoice.total_amount,
        }

        missing_fields = [
            field
            for field, value in required_fields.items()
            if value is None or (
                isinstance(value, str) and not value.strip()
            )
        ]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Hóa đơn chưa đủ thông tin để xác nhận.",
                    "missing_fields": missing_fields,
                },
            )

        invoice.verification_status = "confirmed"
        db.commit()

        return {
            "invoice_id": invoice.id,
            "verification_status": invoice.verification_status,
            "message": "Đã xác nhận hóa đơn thành công."
        }

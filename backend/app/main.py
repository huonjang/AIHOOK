from app.ocr_service import extract_text, extract_fields
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

app = FastAPI(title="AITHOOK API")

# --------------------------------------------------
# Paths and configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{(BASE_DIR / 'invoices.db').as_posix()}"

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


# --------------------------------------------------
# Database model
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="uploaded"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class InvoiceAnalysis(Base):
    __tablename__ = "invoice_analyses"

    invoice_id: Mapped[str] = mapped_column(
        String(36), primary_key=True
    )
    invoice_number: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    invoice_date: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    seller_name: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    total_amount: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    raw_text: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

Base.metadata.create_all(bind=engine)


def serialize_invoice(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "filename": invoice.filename,
        "size": invoice.size,
        "status": invoice.status,
        "created_at": invoice.created_at.isoformat(),
    }


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "AITHOOK API"}


# --------------------------------------------------
# Upload invoice
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

        with Session(engine) as db:
            invoice = Invoice(
                id=invoice_id,
                filename=original_name,
                stored_filename=stored_filename,
                size=size,
                status="uploaded",
                created_at=datetime.now(timezone.utc),
            )

            db.add(invoice)
            db.commit()
            db.refresh(invoice)

            result = serialize_invoice(invoice)

        result["message"] = (
            "Tệp đã được lưu. OCR chưa được thực hiện."
        )
        return result

    except Exception:
        # Không để lại file nếu upload hoặc ghi database thất bại.
        destination.unlink(missing_ok=True)
        raise

    finally:
        await file.close()


# --------------------------------------------------
# List invoices
# --------------------------------------------------

@app.get("/api/invoices")
def list_invoices():
    with Session(engine) as db:
        statement = select(Invoice).order_by(Invoice.created_at.desc())
        invoices = db.scalars(statement).all()

        return [serialize_invoice(invoice) for invoice in invoices]


# --------------------------------------------------
# Preview / retrieve invoice file
# --------------------------------------------------

@app.get("/api/invoices/{invoice_id}/file")
def get_invoice_file(invoice_id: str):
    with Session(engine) as db:
        invoice = db.get(Invoice, invoice_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        stored_filename = invoice.stored_filename
        original_filename = invoice.filename

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
        media_type=media_types.get(extension, "application/octet-stream"),
        filename=original_filename,
        content_disposition_type="inline",
    )


# --------------------------------------------------
# Analyze invoice with OCR
# --------------------------------------------------

@app.post("/api/invoices/{invoice_id}/analyze")
def analyze_invoice(invoice_id: str):
    with Session(engine) as db:
        invoice = db.get(Invoice, invoice_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        file_path = UPLOAD_DIR / invoice.stored_filename

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

        analysis = db.get(InvoiceAnalysis, invoice_id)

        if analysis is None:
            analysis = InvoiceAnalysis(
                invoice_id=invoice_id,
                analyzed_at=datetime.now(timezone.utc),
            )
            db.add(analysis)

        analysis.invoice_number = fields["invoice_number"]
        analysis.invoice_date = fields["invoice_date"]
        analysis.seller_name = fields["seller_name"]
        analysis.total_amount = fields["total_amount"]
        analysis.raw_text = fields["raw_text"]
        analysis.analyzed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(analysis)

        return {
            "invoice_id": invoice_id,
            "status": "analyzed",
            "invoice_number": analysis.invoice_number,
            "invoice_date": analysis.invoice_date,
            "seller_name": analysis.seller_name,
            "total_amount": analysis.total_amount,
            "raw_text": analysis.raw_text,
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "message": "Đã trích xuất văn bản. Vui lòng kiểm tra lại các trường dữ liệu.",
        }


# --------------------------------------------------
# Retrieve saved OCR analysis
# --------------------------------------------------

@app.get("/api/invoices/{invoice_id}/analysis")
def get_invoice_analysis(invoice_id: str):
    with Session(engine) as db:
        invoice = db.get(Invoice, invoice_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        analysis = db.get(InvoiceAnalysis, invoice_id)

        if analysis is None:
            raise HTTPException(
                status_code=404,
                detail="Hóa đơn chưa được phân tích.",
            )

        return {
            "invoice_id": invoice_id,
            "status": "analyzed",
            "invoice_number": analysis.invoice_number,
            "invoice_date": analysis.invoice_date,
            "seller_name": analysis.seller_name,
            "total_amount": analysis.total_amount,
            "raw_text": analysis.raw_text,
            "analyzed_at": analysis.analyzed_at.isoformat(),
        }


# --------------------------------------------------
# Delete invoice
# --------------------------------------------------

@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str):
    with Session(engine) as db:
        invoice = db.get(Invoice, invoice_id)

        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy hóa đơn.",
            )

        file_path = UPLOAD_DIR / invoice.stored_filename

        # Xóa bản ghi trước. Nếu commit thất bại, file vẫn còn.
        db.delete(invoice)
        db.commit()

    file_path.unlink(missing_ok=True)

    return {
        "id": invoice_id,
        "message": "Đã xóa hóa đơn.",
    }

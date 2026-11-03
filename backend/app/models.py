
# backend/app/models.py

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    tax_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="business"
    )


class Invoice(Base):
    __tablename__ = "invoices"

    # SQLite tự sinh ID số nguyên
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id"),
        nullable=False,
        index=True,
    )

    # Thông tin file
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    file_path: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )

    # Dữ liệu hóa đơn trích xuất từ OCR
    invoice_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    invoice_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    seller_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    seller_tax_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    buyer_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    subtotal: Mapped[float | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    tax_amount: Mapped[float | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    total_amount: Mapped[float | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )

    verification_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="needs_review",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship(
        back_populates="invoices"
    )


class InvoiceAnalysis(Base):
    __tablename__ = "invoice_analyses"

    # Lưu ID hóa đơn dưới dạng chuỗi để tương thích
    # với schema invoice_analyses hiện có.
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
